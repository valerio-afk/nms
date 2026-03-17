import werkzeug.datastructures
from nms_shared.enums import UserPermissions
from nms_shared.utils import match_permissions
from werkzeug.datastructures import FileStorage

from . import frontend as bp, NMSBACKEND as BACKEND
from .api.backend_proxy import show_flash
from .api.tasks import PoolExpansionTask
from datetime import datetime
from flask import g, render_template, redirect, url_for, flash, Response, request, session
from flask_babel import _
from flask_babel import format_datetime
from flask_wtf.csrf import validate_csrf
from frontend.utils.decorators import wait
from frontend.utils.forms import ImportPoolForm, CreatePoolForm, AddDisksForm
from nms_shared.msg import ErrorMessages
from pySMART import Device
from typing import Union
from wtforms import ValidationError
import time


# MAIN PAGE

@bp.route('/disks')
# @wait(redirect_to="/disks/new/wait",tag="new_disk")
@wait(redirect_to="/disks/add/wait",tag="add_disk")
def disk_management() -> str:
    disks = BACKEND.disks
    attachable_disks = BACKEND.attachable_disks

    importable_pools = BACKEND.importable_pools

    imports = []

    for p in importable_pools:
        if (p['state'] == "ONLINE"):
            imports.append((p['name'],p['disks'], None, ImportPoolForm()))
        else:
            flash(f"Disk array {p['name']} unrecoverable error: {p['message']}","error")

    current_user = session['user']
    perms = current_user.get("permissions", [])


    snapshots = []

    if (match_permissions(perms,UserPermissions.POOL_TOOLS_SNAPSHOT)):
        snapshots = BACKEND.snapshots


    parameters = {
        "active_page": "disk",
        "disks": disks,
        "pool": BACKEND.is_pool_configured,
        "imported_pools": imports,
        "csp_nonce": g.csp_nonce,
        "snapshots": snapshots
    }


    if (parameters['pool'] == False):
        parameters['new_pool_form'] = CreatePoolForm(disks)
    else:
        parameters['mounted'] = BACKEND.is_mounted
        parameters['scrub'] = BACKEND.scrub_report
        parameters["attachable_disks"] = None if len(attachable_disks) == 0 else AddDisksForm(attachable_disks)

    verify = BACKEND.scrub_info

    if (verify['last'] is None):
        verify['last'] = _("Never")
    else:
        verify['last'] = format_datetime(verify['last'] , "EEEE, d MMMM yyyy HH:mm").title()

    parameters['verify'] = verify



    return render_template("disk_mngt.html", **parameters)

@bp.route('/disks/smart', methods=['POST'])
def smart_disk() -> str:
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
        return redirect(url_for("main.advanced"))

    d = BACKEND.smart_info(request.form.get("disk"))

    return render_template("disk_smart.html", disk = d)


# ACTION PAGES

@bp.route('/disks/add', methods=['POST'])
def add_disk() -> Response:
    attachable_disks = BACKEND.attachable_disks
    form = AddDisksForm(attachable_disks)

    if (form.validate_on_submit()):
        dev = form.disks.data
        task = BACKEND.pool_expand(dev)

        if (task is not None):
            BACKEND.register_task(
                task.get("task_id"),
                ['/disks'],
                metadata="add_disk",
                cls=PoolExpansionTask,
                **task)

    else:
        show_flash(code=ErrorMessages.E_CSRF.name)

    return redirect(url_for("main.disk_management"))

@bp.route('/disks/new',methods=['POST'])
@wait()
def new_pool() -> Response:
    disks = BACKEND.disks
    form = CreatePoolForm(disks)

    if (form.validate_on_submit()):
        redundancy = form.redundancy.data
        encryption = form.encryption.data
        compression = form.compression.data

        pool_name = form.pool_name.data
        dataset_name = form.dataset_name.data

        disks = form.disks.data

        #(pool_name,dataset_name,redundancy,encryption,compression,disks, lang)

        BACKEND.pool_create(pool_name,dataset_name,redundancy,encryption,compression,disks)

    else:
        for e in form.errors:
            for err in form.errors[e]:
                flash(f"{err}","error")

    return redirect(url_for("main.disk_management"))

@bp.route('/disk/import/<string:pool>',methods=['POST'])
def import_pool(pool) -> Response:
    form = ImportPoolForm()

    if form.validate_on_submit():
        try:
            load_key = False
            if (key_data:=form.key.data):
                BACKEND.import_pool_key(key_data.filename,key_data.stream,key_data.mimetype)
                load_key = True

            BACKEND.import_pool(pool,load_key)

            flash(f"Pool {pool} imported successfully.","success")

        except Exception as e:
            flash(f"Error while importing {pool}: {str(e)}","error")
            raise e

    return redirect(url_for("main.disk_management"))

@bp.route('/disk/tool/scrub',methods=['POST'])
def scrub() -> Response:
    try:
        BACKEND.start_scrub()
    except Exception as e:
        flash(str(e),"error")

    return redirect(url_for("main.disk_management"))

@bp.route("/disk/unmount",methods=['POST'])
def unmount() -> Response:
    BACKEND.pool_unmount()
    return redirect(url_for("main.disk_management"))


@bp.route("/disk/mount",methods=['POST'])
def mount() -> Response:
    BACKEND.pool_mount()
    return redirect(url_for("main.disk_management"))

@bp.route("/disk/replace",methods=['POST'])
def replace_disk():
    disk = request.form.get("disk")
    try:
        validate_csrf(request.form.get("csrf_token"))

        if (disk is None):
            show_flash(code=ErrorMessages.E_POOL_DISK_UNAVAL.name,params=[disk])
        else:
            BACKEND.replace_disk(disk)
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    except Exception as e:
        show_flash(type="error", code=ErrorMessages.E_POOL_DISK_REPLACE.name,params=[disk,disk,str(e)])

    time.sleep(0.5)

    return redirect(url_for("main.disk_management"))

@bp.route('/disks/snapshot',methods=['POST'])
def snapshot_disk() -> Response:
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    BACKEND.create_snapshot(timestamp)

    return redirect(url_for("main.disk_management"))

@bp.route('/disks/snapshot/mngt',methods=['POST'])
def snapshot_mngt() -> Response:
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)

    snapshot_to_delete = request.form.get("delete")
    snapsht_to_rollback = request.form.get("rollback")

    if (snapshot_to_delete is not None):
        BACKEND.delete_snapshot(snapshot_to_delete)
    elif (snapsht_to_rollback is not None):
        BACKEND.rollback_snapshot(snapsht_to_rollback)


    return redirect(url_for("main.disk_management"))

# WAIT PAGES

@bp.route('/disks/add/wait')
def add_disk_wait() -> Union[str,Response]:
    tasks = BACKEND.get_tasks_by_metadata("add_disk")

    if len(tasks) == 0:
        return redirect(url_for("main.disk_management"))

    add_disk_task = tasks.pop()

    return render_template("wait.determinate.html",
                           active_page="disk",
                           refresh_to=url_for("main.disk_management"),
                           task_id=add_disk_task.task_id,
                           csp_nonce=g.csp_nonce)

@bp.route('/disks/replace/wait')
def replace_disk_wait() -> Union[str,Response]:
    tasks = BACKEND.get_tasks_by_metadata("resilver")

    if len(tasks) == 0:
        return redirect(url_for("main.disk_management"))

    resilver_task = tasks.pop()

    return render_template("wait.determinate.html",
                           active_page="disk",
                           refresh_to=url_for("main.disk_management"),
                           task_id=resilver_task.task_id,
                           csp_nonce=g.csp_nonce)


