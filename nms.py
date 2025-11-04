import os
from flask import Flask, render_template, redirect, url_for, jsonify, request
from disk import DiskStatus
from widget import render_widget,get_widgets_html,get_widgets_css_files
from random import randint
from backend import BACKEND, celery_init_app, __version__
from tasks import create_pool, NMSTask
from decorators import wait

app = Flask("NMS")
app.config.from_mapping(
    CELERY=dict(
        broker_url="redis://localhost:6379/0",
        result_backend="redis://localhost:6379/1",
    ),
)
celery_app = celery_init_app(app)



def widget_disk_usage():
    return render_widget("disk_usage",usage=randint(0,100))

@app.route('/async/widgets/disk_usage')
def async_widget_disk_usage():
    return widget_disk_usage()[0]


def widget_disk_overview():
    disks = BACKEND.get_disks()
    pool_options = BACKEND.get_pool_options() if BACKEND.is_pool_configured() else []

    return render_widget("disk_list",disks=disks,pool_options=pool_options)

@app.route('/async/widgets/system_info')
def async_widget_sys_info():
    return widget_sys_info()[0]


def widget_sys_info():
    sys_info = BACKEND.system_information

    return render_widget("system_info",system_info=sys_info)

@app.route('/async/widgets/disk_overview')
def async_widget_disk_overview():
    return widget_disk_overview()[0]

def widget_network_overview():
    ifaces = BACKEND.iface_status()
    return render_widget("network_list",ifaces=ifaces)

@app.route('/async/widgets/network_overview')
def async_widget_network_overview():
    return widget_network_overview()[0]

def widget_access_overview():
    services = BACKEND.get_access_services()
    return render_widget("access_list",services=services)

@app.template_filter("disk_charm")
def disk_charm(disk_status:DiskStatus):
    match (disk_status):
        case DiskStatus.NEW: return "✴️"
        case DiskStatus.ONLINE: return "🟢"
        case DiskStatus.OFFLINE: return "🔴"
        case DiskStatus.CORRUPTED: return "⚫"

@app.template_filter("enabled_fmt")
def enabled_fmt(status:bool):
    fmt = "Enabled" if status else "Disabled"
    badge = "success" if status else "danger"
    return f'<span class="badge bg-{badge}">{fmt}</span>'

@app.template_filter("human_readable_bytes")
def human_readable_bytes(bytes:int):
    magnitutes = ["B", "KB", "MB", "GB", "TB"]

    i = 0

    while ( (bytes>=1024) and (i<len(magnitutes)) ):
        bytes /= 1024
        i+=1

    return f"{bytes:.2f}{magnitutes[i]}"




@app.route('/disks/new',methods=['POST'])
@wait()
def new_pool():

    redundancy = 'redundancy' in request.form  # True if checked, False if not
    encryption = 'encryption' in request.form
    compression = 'compression' in request.form

    task = create_pool.delay(redundancy,encryption,compression)
    BACKEND.append_task(NMSTask(task.task_id,"/disks"))
    return redirect(url_for("disk_management"))

@app.route('/disks')
@wait(redirect_to="/disks/new/wait")
def disk_management():
    disks = BACKEND.get_disks()
    completed_tasks = BACKEND.pop_completed_tasks("/disks")
    pool = BACKEND.is_pool_configured()

    return render_template("disk_mngt.html",active_page="disk",disks=disks,tasks=completed_tasks, pool=pool)


@app.route('/disks/new/wait')
def new_pool_wait():
    return render_template("wait.indeterminate.html",
                           active_page="disk",
                           refresh_to="/disks",
                           extra_css=["pacman.css"],
                           waiting_message="The creation of a new disk array may take some time. Please wait...")


@app.route('/')
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



@app.route('/check_tasks', methods=['POST'])
def check_tasks():
    data = request.get_json()

    if not data or 'path' not in data:
        return jsonify({"error": "Missing 'path' parameter"}), 400

    path = data['path']

    tasks = BACKEND.get_tasks_by_path(path)

    return jsonify(tasks)

if __name__ == '__main__':
    app.run(debug=True)
