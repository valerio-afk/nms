import datetime
import os
from flask import render_template, redirect, url_for, jsonify, request, flash, Blueprint
from disk import DiskStatus
from widget import render_widget,get_widgets_html,get_widgets_css_files
from random import randint
from backend import BACKEND
from tasks import create_pool, NMSTask
from decorators import wait

bp = Blueprint('main',__name__)

def widget_disk_usage():
    return render_widget("disk_usage",usage=randint(0,100))

@bp.route('/async/widgets/disk_usage')
def async_widget_disk_usage():
    return widget_disk_usage()[0]


def widget_disk_overview():
    disks = BACKEND.get_disks()
    pool_options = BACKEND.get_pool_options() if BACKEND.is_pool_configured() else []

    return render_widget("disk_list",disks=disks,pool_options=pool_options)

@bp.route('/async/widgets/system_info')
def async_widget_sys_info():
    return widget_sys_info()[0]


def widget_sys_info():
    sys_info = BACKEND.system_information

    return render_widget("system_info",system_info=sys_info)

@bp.route('/async/widgets/disk_overview')
def async_widget_disk_overview():
    return widget_disk_overview()[0]

def widget_network_overview():
    ifaces = BACKEND.iface_status()
    return render_widget("network_list",ifaces=ifaces)

@bp.route('/async/widgets/network_overview')
def async_widget_network_overview():
    return widget_network_overview()[0]

def widget_access_overview():
    services = BACKEND.get_access_services()
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

@bp.route('/disk/tool/scrub')
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

    #has_redundancy = BACKEND.has_redundancy
    verify = BACKEND.get_scrub_info
    # check = BACKEND.get_check_info


    if (verify['last'] is None):
        verify['last'] = "Never"
    else:
        verify['last'] = datetime.datetime.fromtimestamp(verify['last']).strftime("%c")

    # if (check['last'] is None):
    #     check['last'] = "Never"
    # else:
    #     check['last'] = datetime.datetime.fromtimestamp(check['last']).strftime()

    return render_template("disk_mngt.html",
                           active_page="disk",
                           disks=disks,
                           pool=pool,
                           verify=verify
                           # check=check
                           )


@bp.route('/disks/new/wait')
def new_pool_wait():
    return render_template("wait.indeterminate.html",
                           active_page="disk",
                           refresh_to="/disks",
                           extra_css=["pacman.css"],
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

@bp.before_request
def check_flash_messages_from_tasks():
    tasks = BACKEND.pop_completed_tasks()

    reload_config = False

    for t in tasks:
        flash(t.result,"success" if t.successful else "error")
        reload_config = True


    if (reload_config):
        BACKEND.load_configuration_file()