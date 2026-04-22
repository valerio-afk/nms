from nms_shared.msg import EVENT_NAMES, ACTION_CATEGORIES, ACTION_NAMES, CONTEXT_VARS
from .api.backend_proxy import show_flash
from .import NMSBACKEND as BACKEND, frontend as bp
from ansi2html import Ansi2HTMLConverter
from flask import render_template, redirect, url_for, request, flash, g, send_file, session, Response
from flask_babel import format_datetime, _
from flask_wtf.csrf import  validate_csrf
from frontend.utils.decorators import wait
from frontend.utils.widget import render_widget,get_widgets_html,get_widgets_css_files
from io import BytesIO
from nms_shared import ErrorMessages, EventNames
from nms_shared.constants import HTTP_REPEAT_HEADER
from nms_shared.enums import LogFilter, UserPermissions
from nms_shared.utils import match_permissions
from nms_shared.msg import parse_msg, PARAMS_NAMES
from typing import Optional, Dict, Callable, Any, Union, List, Tuple
from werkzeug.datastructures import ImmutableMultiDict
from wtforms import ValidationError

import base64
import datetime


def risky_operation_reauth(operation:str,callback:Callable[[str, ImmutableMultiDict],Any]) -> Optional[Response]:
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:
        authorisation = session.pop("dz_authorisation",None)

        if (authorisation is None):
            return redirect(url_for("main.reauth",operation=operation))

        else:
            if ((token:=BACKEND.get_session_token(operation)) is not None):
                form = request.form
                callback(token,form)
            else:
                show_flash(code=ErrorMessages.E_AUTH_INVALID.name)

def widget_system_admin():
    permissions = session.get("user").get("permissions",[])

    perms = {
        'logs': match_permissions(permissions,UserPermissions.SYS_ADMIN_LOGS),
        'systemctl' : match_permissions(permissions,UserPermissions.SYS_ADMIN_SYSTEMCTL),
        'pool_info': match_permissions(permissions,UserPermissions.POOL_CONF_GET_INFO),
        'events': match_permissions(permissions,UserPermissions.SYS_ADMIN_EVENTS)

    }

    return render_widget("sys_admin",permissions=perms,encrypted=BACKEND.has_encryption)

def widget_system_updates(hedaers:Optional[Dict]=None):
    apt = {
        'last_update' : BACKEND.last_apt_time,
        'updates': BACKEND.system_updates,
        'state': None,
        'nms': BACKEND.latest_nms_updates,
    }

    if (apt['last_update'] is not None):
        apt['last_update'] = format_datetime(apt['last_update'], "EEEE, d MMMM yyyy HH:mm").title()
    else:
        apt['last_update'] = _("Never")

    tasks = BACKEND.get_tasks_by_path("/advanced/apt")

    repeat = False

    for t in tasks:
        if (t.metadata is not None):
            apt['state'] = t.metadata
            repeat = True

    if (hedaers is not None):
        hedaers[HTTP_REPEAT_HEADER] = repeat

    return render_widget("apt", **apt)

def widget_danger_zone():
    permissions = session.get("user").get("permissions", [])

    perms = {
        'format_pool': match_permissions(permissions, UserPermissions.POOL_CONF_FORMAT),
        'format_disk': match_permissions(permissions, UserPermissions.POOL_DISKS_FORMAT),
        'destroy': match_permissions(permissions, UserPermissions.POOL_CONF_DESTROY),
        'recovery': match_permissions(permissions, UserPermissions.POOL_TOOLS_RECOVERY)
    }


    choices = []

    if (perms.get('format_disk',False)):
        disks = BACKEND.system_disks
        choices = [(d.path, d.name) for d in disks]

    return render_widget("danger_zone",permissions=perms,disks=choices)


def create_fields_event_action(event_name:str,action_tag:str,default_values:Optional[Dict[str,Any]]=None) -> Optional[Tuple[List[str],Dict[str, str]]]:
    parameters = []
    events_information = BACKEND.events

    event = None

    for e in events_information:
        if (e.get("event") == event_name):
            event = e

    if (event is None):
        return None

    action = None

    for a in event.get("allowed_actions",[]):
        if (a.get("tag") == action_tag):
            action = a

    if (action is None):
        return None


    for parameter, specs in action.get("parameters", {}).items():
        metatype = specs.get("metatype", "")
        param_form = ""
        kwargs = {}

        if (default_values is not None):
            if ((value:=default_values.get(parameter)) is not None):
                kwargs['default_value'] = value

        match (metatype):
            case "string":
                param_form = render_template("event.parameter.string.html",
                                             label=parse_msg(PARAMS_NAMES.get(parameter)),
                                             parameter=parameter,
                                             **kwargs)
            case "bool":
                param_form = render_template("event.parameter.bool.html",
                                             label=parse_msg(PARAMS_NAMES.get(parameter)),
                                             parameter=parameter,
                                             **kwargs)
            case "user":
                all_users = BACKEND.users
                param_form = render_template("event.parameter.user.html",
                                             users=all_users,
                                             label=parse_msg(PARAMS_NAMES.get(parameter)),
                                             parameter=parameter,
                                             **kwargs)

        parameters.append(param_form)

    context:Dict[str,str] = {}
    for v in action.get("context", []):
        context[v] = parse_msg(CONTEXT_VARS.get(v))

    return parameters, context

def parse_event_form(event:Optional[str],action:Optional[str]):

    if (event is None):
        show_flash(code=ErrorMessages.E_EVENT_INVALID.name)
        raise Exception()
    if (action is None):
        show_flash(code=ErrorMessages.E_ACTION_INVALID.name)
        raise Exception()

    events_information = BACKEND.events
    expected_parameters: Optional[Dict[str, Dict[str, str]]] = None

    import sys

    for e in events_information:
        if (e.get("event") == event):
            print("I am here bitches",file=sys.stderr)
            for a in e.get("allowed_actions",[]):
                if (action == a.get("tag")):
                    expected_parameters = a.get("parameters", None)
                    break
            break

    if (expected_parameters is None):
        show_flash(code=ErrorMessages.E_ACTION_INVALID.name)
        raise Exception()

    parameters = {}

    for p, specs in expected_parameters.items():
        metatype = specs.get("metatype", None)
        match (metatype):
            case "bool":
                parameters[p] = True if (f"param_{p}" in request.form) else False
            case _:
                parameters[p] = request.form.get(f"param_{p}", None)

    return parameters

@bp.route('/async/widgets/apt')
def async_widget_system_updates():
    headers = {}
    html = widget_system_updates(headers)[0]

    return html,200,headers

# MAIN PAGE

@bp.route("/advanced")
@wait(redirect_to="/advanced/nms/wait",tag="nms_update")
def advanced():
    advanced_widgets = []

    perms = session.get("user").get("permissions",[])

    if (advanced:=match_permissions(perms,UserPermissions.CLIENT_DASHBOARD_ADVANCED)):
        advanced_widgets.append(widget_system_admin())

    if (match_permissions(perms,UserPermissions.SYS_ADMIN_UPDATES)):
        advanced_widgets.append(widget_system_updates())


    if (BACKEND.is_pool_configured and advanced):
        advanced_widgets.append(widget_danger_zone())

    return render_template("advanced.html",
                           csp_nonce=g.csp_nonce,
                           widgets=get_widgets_html(advanced_widgets),
                           extra_css=get_widgets_css_files(advanced_widgets),
                           active_page="advanced"
                           )

# SUB PAGES

@bp.route('/advanced/logs', defaults={'log': 'flask'})
@bp.route('/advanced/logs/<string:log>')
def system_logs(log):
    match (log):
        case "nginx":
            log_filter = LogFilter.WEB_SERVER
        case "backend":
            log_filter = LogFilter.BACKEND
        case _:
            log_filter = LogFilter.FRONTEND

    start = request.args.get('start')
    end = request.args.get('end')


    if (end is None):
       until = datetime.datetime.now().timestamp()
       end = datetime.datetime.fromtimestamp(until).strftime("%Y-%m-%d %H:%M:%S")
    else:
       until = datetime.datetime.fromisoformat(end).timestamp()

    if (start is None):
        since = until - datetime.timedelta(hours=1).total_seconds()
        start = datetime.datetime.fromtimestamp(since).strftime("%Y-%m-%d %H:%M:%S")
    else:
        since = datetime.datetime.fromisoformat(start).timestamp()

    since = int(since)
    until = int(until)

    logs = BACKEND.get_logs(log_filter,since=since,until=until)

    conv = Ansi2HTMLConverter()
    logs = conv.convert(logs,full=False)


    return render_template("advanced.logs.html",
                           active=log_filter.value,
                           log_html=logs,
                           breadcrumbs=[
                               (_("Advanced"), url_for("main.advanced")),
                               (_("System Logs"), None)
                           ],
                           csp_nonce=g.csp_nonce,
                           date_filter={"start":start,"end":end},
                           active_page="advanced")

@bp.route('/advanced/events')
def events():

    events_information = BACKEND.events
    events_list = {}
    allowed_actions = {}
    action_forms = {}

    for e in events_information:
        name = e.get("event","")
        category = name.split(".")[0]

        category_lbl = EventNames.get_event(EventNames(category))
        event_lbl = EventNames.get_event(EventNames(name))

        if (category_lbl not in events_list.keys()):
            events_list[category_lbl] = {}

        events_list[category_lbl].update({name: event_lbl})
        allowed_actions[name] = {}



        for a in e.get("allowed_actions", {}):
            tag = a.get("tag","-")

            action_category_lbl = parse_msg(ACTION_CATEGORIES.get(a.get("category","-")))

            if (allowed_actions[name].get( action_category_lbl ) is None):
                allowed_actions[name][action_category_lbl] = {}

            allowed_actions[name][action_category_lbl].update({tag: parse_msg(ACTION_NAMES.get(tag))})
            action_forms[f"{name}-{tag}"] = create_fields_event_action(name,tag)


    registered_events = BACKEND.registered_events

    for x in registered_events:
        x['form'] = create_fields_event_action(x.get("event"),x.get("action"),x.get("parameters",{}))



    return render_template("events.html",
                           breadcrumbs=[
                               (_("Advanced"), url_for("main.advanced")),
                               (_("Events"), None)
                           ],
                           events=events_list,
                           registered_events = registered_events,
                           allowed_actions=allowed_actions,
                           action_forms=action_forms,
                           csp_nonce=g.csp_nonce,
                           active_page="advanced")

@bp.route('/advanced/events/new',methods=['POST'])
def add_event() -> Response:
    try:
        validate_csrf(request.form.get("csrf_token"))

        event = request.form.get("event")
        action = request.form.get("allowed_actions")

        parameters = parse_event_form(event,action)

        BACKEND.add_event(
            event_name=event,
            action_name=action,
            **parameters
        )

    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    except Exception:
        ...

    return redirect(url_for("main.events"))

@bp.route('/advanced/events/update',methods=['POST'])
def update_event() -> Response:
    try:
        validate_csrf(request.form.get("csrf_token"))

        uuid = request.form.get("uuid")

        registered_events = BACKEND.registered_events

        event = None


        for e in registered_events:
            if (e['uuid'] == uuid):
                event = e
                break

        if ((uuid is None) or (event is None)):
            raise ValueError()

        name = event.get("event")
        action = event.get("action")

        parameters = parse_event_form(name,action)

        BACKEND.update_event(
            uuid=uuid,
            **parameters
        )

    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)

    except ValueError:
        show_flash(code=ErrorMessages.E_EVENT_INVALID.name)
    except Exception as e:
        raise e


    return redirect(url_for("main.events"))

@bp.route("/advanced/events/status/<string:action>",methods=['POST'])
def event_change_status(action: str) -> Response:
    try:
        validate_csrf(request.form.get("csrf_token"))
        uuid = request.form.get("uuid")
        match (action.lower()):
            case "up":
                BACKEND.enable_event(uuid)
            case "down":
                BACKEND.disable_event(uuid)

    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)


    return redirect(url_for("main.events"))

@bp.route("/advanced/events/delete",methods=['POST'])
def delete_event() -> Response:
    try:
        validate_csrf(request.form.get("csrf_token"))
        uuid = request.form.get("uuid")
        BACKEND.delete_event(uuid)

    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)

    return redirect(url_for("main.events"))


# # ACTIONS

@bp.route("/advanced/restart-systemd",methods=['POST'])
def restart_systemd():
    flash("System services are being restarted. If the web interface glitched, that is a good sign it's working.")
    BACKEND.restart_systemd_services()
    return redirect(url_for("main.advanced"))

@bp.route("/advanced/get-key",methods=['POST'])
def get_tank_key() -> Response:
    key = BACKEND.encryption_key

    if (key is None):
        show_flash(code=ErrorMessages.E_POOL_KEY.name)
        return redirect(url_for("main.advanced"))

    raw_data = base64.b64decode(key)
    key_fname = f"{BACKEND.dataset_name}.key"

    return send_file(BytesIO(raw_data),as_attachment=True,download_name=key_fname,mimetype="application/octet-stream")



@bp.route('/advanced/format',methods=['POST'])
def format():
    return risky_operation_reauth("format",lambda token,_ : BACKEND.simulate_format(token)) or redirect(url_for("main.advanced"))

@bp.route('/advanced/destroy',methods=['POST'])
def zpool_destroy():
    return risky_operation_reauth("destroy", lambda token,_: BACKEND.pool_destroy(token)) or redirect(url_for("main.advanced"))

@bp.route('/advanced/recover',methods=['POST'])
def zpool_recover():
    return risky_operation_reauth("recover", lambda token,_: BACKEND.pool_recover(token)) or redirect(url_for("main.advanced"))

@bp.route('/advanced/format_disk',methods=['POST'])
def zpool_format_disk():
    return risky_operation_reauth("format-disk", lambda token,form: BACKEND.format_disk(form.get("option"),token)) or redirect(url_for("main.advanced"))


@bp.route('/advanced/apt',methods=['POST'])
def apt_get():
    action = request.form.get("action",None)
    task = None

    if (action == "update"):
        task = BACKEND.apt_get_update()
    elif (action == "upgrade"):
        task = BACKEND.apt_get_upgrade()

    if task is None:
        show_flash(code=ErrorMessages.E_APT_GET.name)
    else:
        try:
            task_id = task.get("task_id")
            BACKEND.register_task(task_id,pages=["/advanced/apt"],metadata=action,**task)
        except Exception as e:
            show_flash(code=ErrorMessages.E_APT_GET.name,params=[str(e)])

    return redirect(url_for("main.advanced"))

@bp.route('/advanced/nms',methods=['POST'])
def nms_updates():
    action = request.form.get("action",None)


    if (action == "update"):
        BACKEND.check_nms_updates()
    elif (action == "upgrade"):
        from logging import getLogger
        # log = getLogger("nms.webapp")

        task = BACKEND.update_nms()
        # log.error(task)

        if task is None:
            show_flash(code=ErrorMessages.E_APT_GET.name)
        else:

            try:
                task_id = task.get("task_id")
                BACKEND.register_task(task_id,
                                      pages=["/advanced"],
                                      metadata="nms_update",**task)
            except Exception as e:
                show_flash(code=ErrorMessages.E_APT_GET.name,params=[str(e)])

    return redirect(url_for("main.advanced"))


@bp.route('/advanced/nms/wait')
def nms_updates_wait() -> Union[str,Response]:
    tasks = BACKEND.get_tasks_by_metadata("nms_update")

    if len(tasks) == 0:
        return redirect(url_for("main.advanced"))

    update_task = tasks.pop()

    return render_template("wait.indeterminate.html",
                           active_page="advanced",
                           refresh_to=url_for("main.advanced"),
                           task_id=update_task.task_id,
                           waiting_message=_("Update in progress. At the end of this operation, NMS will be restarted. You may refresh this page. If it becomes unresponsive, wait a few more seconds and retry."),
                           csp_nonce=g.csp_nonce)