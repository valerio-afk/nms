import datetime

from celery.worker.control import active
from flask import render_template, redirect, url_for, jsonify, request, flash, Blueprint, g

from forms import AccessServiceForm
from widget import render_widget,get_widgets_html,get_widgets_css_files
from backend import BACKEND, LogFilter
from tasks import create_pool, NMSTask
from decorators import wait

bp = Blueprint('main',__name__)

def widget_disk_usage():
    pool_capacity = BACKEND.get_pool_capacity
    used = pool_capacity['used']
    total = pool_capacity['total']

    capacity = int(used/total*1000)/10 if total > 0 else 0

    return render_widget("disk_usage",used=used, total=total, capacity=capacity)

@bp.route('/async/widgets/disk_usage')
def async_widget_disk_usage():
    return widget_disk_usage()[0]


def widget_disk_overview():
    disks = BACKEND.get_disks()
    pool_options = BACKEND.get_pool_options() if BACKEND.is_pool_configured() else []

    return render_widget("disk_list",disks=disks,pool_options=pool_options)
@bp.route('/async/widgets/disk_overview')
def async_widget_disk_overview():
    return widget_disk_overview()[0]

@bp.route('/async/widgets/system_info')
def async_widget_sys_info():
    return widget_sys_info()[0]


def widget_sys_info():
    sys_info = BACKEND.system_information

    return render_widget("system_info",system_info=sys_info)



def widget_network_overview():
    ifaces = BACKEND.iface_status()
    return render_widget("network_list",ifaces=ifaces)

@bp.route('/async/widgets/network_overview')
def async_widget_network_overview():
    return widget_network_overview()[0]

def widget_access_overview():
    access_services = BACKEND.get_access_services

    services = [(name.upper(),False) for name,obj in access_services.items()]

    return render_widget("access_list",services=services)


# def widget_disk_tools():
#     has_redundancy = BACKEND.has_redundancy
#
#     verify = BACKEND.get_verify_info
#
#     print("asdasdasdasd")
#
#     if (verify['last'] is None):
#         verify['last'] = "Never"
#     else:
#         verify['last'] = datetime.datetime.fromtimestamp(verify['last']).strftime()
#
#
#     return render_widget("disk_tools",redundancy = has_redundancy,verify=verify)

@bp.route('/disk/tool/scrub',methods=['POST'])
def scrub():
    try:
        BACKEND.start_scrub()
    except Exception as e:
        flash(str(e),"error")

    return redirect(url_for("main.disk_management"))



@bp.route('/disks/new',methods=['POST'])
@wait()
def new_pool():

    redundancy = 'redundancy' in request.form  # True if checked, False if not
    encryption = 'encryption' in request.form
    compression = 'compression' in request.form

    task = create_pool.delay(redundancy,encryption,compression)
    BACKEND.append_task(NMSTask(task.task_id,"/disks"))
    return redirect(url_for("main.disk_management"))


@bp.route('/disks')
@wait(redirect_to="/disks/new/wait")
def disk_management():
    disks = BACKEND.get_disks()
    pool = BACKEND.is_pool_configured()

    verify = BACKEND.get_scrub_info

    if (verify['last'] is None):
        verify['last'] = "Never"
    else:
        verify['last'] = datetime.datetime.fromtimestamp(verify['last']).strftime("%c")

    scrub_report = BACKEND.get_last_scrub_report()



    return render_template("disk_mngt.html",
                           active_page="disk",
                           disks=disks,
                           pool=pool,
                           verify=verify,
                           scrub = scrub_report,
                           csp_nonce=g.csp_nonce
                           # check=check
                           )


@bp.route('/disks/new/wait')
def new_pool_wait():
    return render_template("wait.indeterminate.html",
                           active_page="disk",
                           refresh_to="/disks",
                           extra_css=["pacman.css"],
                           csp_nonce=g.csp_nonce,
                           waiting_message="The creation of a new disk array may take some time. Please wait...")


@bp.route('/')
def dashboard():
    dashboard_widgets = [
        widget_disk_overview(),
        widget_network_overview(),
        widget_access_overview(),
        widget_sys_info()
    ]

    if (BACKEND.is_pool_configured()):
        dashboard_widgets.insert(0,widget_disk_usage())


    return render_template("dashboard.html",
                           active_page="dashboard",
                           csp_nonce=g.csp_nonce,
                           widgets=get_widgets_html(dashboard_widgets),
                           extra_css = get_widgets_css_files(dashboard_widgets)
                           )



@bp.route('/check_tasks', methods=['POST'])
def check_tasks():
    data = request.get_json()

    if not data or 'path' not in data:
        return jsonify({"error": "Missing 'path' parameter"}), 400

    path = data['path']

    tasks = BACKEND.get_tasks_by_path(path)

    return jsonify(tasks)


@bp.route("/reboot", methods=['POST'])
def reboot():

    try:
        BACKEND.reboot()
    except Exception as e:
        flash(str(e),"error")

    return redirect(url_for('main.dashboard'))


@bp.route("/shutdown", methods=['POST'])
def shutdown():
    BACKEND.shutdown()

    return redirect(url_for('main.dashboard'))

@bp.route("/access/update/<string:service>",methods=['POST'])
def change_access_settings(service):
    serv = BACKEND.get_access_services.get(service,None)

    if (serv is None):
        flash(f"Service `{service}` not recognised","error")
        return redirect(url_for("main.access"))

    form = AccessServiceForm(serv.is_active)

    if (form.validate_on_submit()):
        raise Exception("All good")
    elif (request.method == 'POST'):
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, "error")

    return redirect(url_for("main.access"))


@bp.route("/access")
def access():

    ssh_service = BACKEND.get_access_services['ssh']
    ssh_enabled = ssh_service.is_active

    ssh_form =  AccessServiceForm(enabled=ssh_enabled)
    ssh_form.port.default = ssh_service.get("port")
    ssh_form.username.default = ssh_service.get("username")
    ssh_form.process()

    ssh_widget = render_widget("access",service="ssh",service_enabled=ssh_enabled,form=ssh_form)

    widgets = [ssh_widget[0]]

    return render_template("access.html",active_page="access",services=widgets)

@bp.route("/advanced")
def advanced():
    return render_template("advanced.html",csp_nonce=g.csp_nonce,active_page="advanced")

@bp.route("/advanced/restart-systemd",methods=['POST'])
def restart_systemd():
    flash("System services are being restarted. If the web interface glitched, that is a good sign it's working.")
    BACKEND.restart_systemd_services()
    return redirect(url_for("main.advanced"))

@bp.route('/advanced/logs', defaults={'log': 'flask'})
@bp.route('/advanced/logs/<string:log>')
def system_logs(log):
    log_filter = LogFilter.FLASK

    match (log):
        case "backend":
            log_filter = LogFilter.BACKEND
        case "celery":
            log_filter = LogFilter.CELERY
        case "sudo_daemon":
            log_filter = LogFilter.SUDODAEMON

    logs = BACKEND.get_logs(log_filter)

    return render_template("advanced.logs.html",active=log,log_html=logs,csp_nonce=g.csp_nonce,active_page="advanced")



@bp.before_request
def check_flash_messages_from_tasks():
    tasks = BACKEND.pop_completed_tasks()

    reload_config = False

    for t in tasks:
        flash(t.result,"success" if t.successful else "error")
        reload_config = True


    if (reload_config):
        BACKEND.load_configuration_file()

@bp.after_request
def scrub_checker(response):

    BACKEND.check_scrub_status()
    return response