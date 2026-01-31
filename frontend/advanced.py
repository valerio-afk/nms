from nms_shared import ErrorMessages
from nms_shared.constants import HTTP_REPEAT_HEADER
from .import NMSBACKEND as BACKEND, frontend as bp
from .api.backend_proxy import show_flash
from flask import render_template, redirect, url_for, request, flash, g, send_file, session, abort
from flask_wtf.csrf import generate_csrf, validate_csrf
from io import BytesIO
from widget import render_widget,get_widgets_html,get_widgets_css_files
from wtforms import ValidationError
from urllib.parse import quote, unquote
from typing import Optional, Dict
import os
import time




def widget_system_admin():

    return render_widget("sys_admin",encrypted=BACKEND.has_encryption)

def widget_system_updates(hedaers:Optional[Dict]=None):
    apt = {
        'csrf_token': generate_csrf(),
        'last_update' : BACKEND.last_apt_time,
        'updates': BACKEND.system_updates,
        'state': None
    }

    if (apt['last_update'] is not None):
        apt['last_update'] = apt['last_update'].strftime("%c")

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
    disks = BACKEND.system_disks

    choices = [(d.path, d.name) for d in disks]

    return render_widget("danger_zone",disks=choices)


@bp.route('/async/widgets/apt')
def async_widget_system_updates():
    headers = {}
    html = widget_system_updates(headers)[0]

    return html,200,headers

# MAIN PAGE

@bp.route("/advanced")
def advanced():

    dashboard_widgets = [
        widget_system_admin(),
        widget_system_updates()
    ]

    if BACKEND.is_pool_configured:
        dashboard_widgets.append(widget_danger_zone())

    return render_template("advanced.html",
                           csp_nonce=g.csp_nonce,
                           widgets=get_widgets_html(dashboard_widgets),
                           extra_css=get_widgets_css_files(dashboard_widgets),
                           active_page="advanced"
                           )

# SUB PAGES

@bp.route('/advanced/logs', defaults={'log': 'flask'})
@bp.route('/advanced/logs/<string:log>')
def system_logs(log):
    log_filter = LogFilter.FLASK

    match (log):
        case "backend_client":
            log_filter = LogFilter.BACKEND
        case "celery":
            log_filter = LogFilter.CELERY
        case "sudo_daemon":
            log_filter = LogFilter.SUDODAEMON

    logs = BACKEND.get_logs(log_filter)

    return render_template("advanced.logs.html",active=log,log_html=logs,csp_nonce=g.csp_nonce,active_page="advanced")

# ACTIONS
@bp.route("/advanced/reset-otp",methods=['POST'])
def reset_otp():
    session.clear()
    BACKEND.set_otp_secret(None)
    return redirect(url_for("main.login"))

@bp.route("/advanced/restart-systemd",methods=['POST'])
def restart_systemd():
    flash("System services are being restarted. If the web interface glitched, that is a good sign it's working.")
    BACKEND.restart_systemd_services()
    return redirect(url_for("main.advanced"))

@bp.route("/advanced/get-key",methods=['POST'])
def get_tank_key():
    key = BACKEND.get_tank_key()

    if (key is None):
        flash("Unable to retrieve the encryption key","error")
        return redirect(url_for("main.advanced"))

    return send_file(BytesIO(key),as_attachment=True,download_name=os.path.split(BACKEND.key_filename)[1],mimetype="application/octet-stream")



@bp.route('/advanced/format',methods=['POST'])
def format():
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        raise Exception("CSRF validation failed")
        abort(400)

    authorisation = session.pop("dz_authorisation",None)

    if (authorisation is None):
        return redirect(url_for("main.reauth",operation="format"))

    else:
        if (time.time() - authorisation['timestamp']) < 60:
            if (authorisation['operation'] == "format"):
                try:
                    BACKEND.simulate_format()
                    flash("Disk array formatted.","success")
                except Exception as e:
                    flash(f"Error while formatting disk array: {str(e)}","error")
            else:
                flash(f"Invalid authorisation", "error")

        else:
            flash("Authorisation token expired","error")

        return redirect(url_for("main.advanced"))

@bp.route('/advanced/destroy',methods=['POST'])
def zpool_destroy():
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        flash("CSRF validation failed","error")
        return redirect(url_for("main.advanced"))

    authorisation = session.pop("dz_authorisation",None)

    if (authorisation is None):
        return redirect(url_for("main.reauth",operation="destroy"))

    else:
        if (time.time() - authorisation['timestamp']) < 60:
            if (authorisation['operation'] == "destroy"):
                try:
                    BACKEND.destroy_tank()
                    flash("Disk array deleted.","success")
                except Exception as e:
                    flash(f"Error while deleting disk array: {str(e)}","error")
            else:
                flash(ErrorMessage.get_error(ErrorMessage.E_AUTH_INVALID), "error")

        else:
            flash(ErrorMessage.get_error(ErrorMessage.E_AUTH_EXPIRED),"error")

        return redirect(url_for("main.advanced"))

@bp.route('/advanced/recover',methods=['POST'])
def zpool_recover():
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        flash("CSRF validation failed","error")
        return redirect(url_for("main.advanced"))

    authorisation = session.pop("dz_authorisation",None)

    if (authorisation is None):
        return redirect(url_for("main.reauth",operation="recover"))

    else:
        if (time.time() - authorisation['timestamp']) < 60:
            if (authorisation['operation'] == "recover"):
                try:
                    BACKEND.recover()
                    flash(SuccessMessage.get_message(SuccessMessage.S_RECOVERY),"success")
                except Exception as e:
                    flash(ErrorMessage.get_error(ErrorMessage.E_POOL_RECOVERY,str(e)),"error")
            else:
                flash(ErrorMessage.get_error(ErrorMessage.E_AUTH_INVALID), "error")

        else:
            flash(ErrorMessage.get_error(ErrorMessage.E_AUTH_EXPIRED),"error")

        return redirect(url_for("main.advanced"))

@bp.route('/advanced/format_disk',methods=['POST'])
def zpool_format_disk():
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        flash("CSRF validation failed","error")
        return redirect(url_for("main.advanced"))

    authorisation = session.pop("dz_authorisation",None)

    option = request.form.get("option",None)

    if option is None:
        raise Exception("Invalid disk to format")

    auth_code = quote(f"format:{option.replace("/","+")}")


    if (authorisation is None):
        return redirect(url_for("main.reauth",operation=auth_code))

    else:
        if (time.time() - authorisation['timestamp']) < 60:
            if (authorisation['operation'] == unquote(auth_code)):
                try:
                    BACKEND.format_disk(option)
                    flash(f"Disk {option} formatted successfully.","success")
                except Exception as e:
                    flash(f"Error while formatting {option}: {str(e)}","error")
            else:
                flash(f"Invalid authorisation", "error")

        else:
            flash("Authorisation token expired","error")

        return redirect(url_for("main.advanced"))


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


