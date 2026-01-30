from . import frontend as bp, NMSBACKEND as BACKEND
# from .tasks import  expand_pool, create_pool
from datetime import datetime
from flask import g, render_template, redirect, url_for, flash, Response, request
from flask_wtf.csrf import validate_csrf
from flask_babel import _, get_locale
from forms import ImportPoolForm, CreatePoolForm, AddDisksForm
from frontend.decorators import wait
from pySMART import Device
from typing import Union
from wtforms import ValidationError


# MAIN PAGE

@bp.route('/disks')
@wait(redirect_to="/disks/new/wait",tag="new_disk")
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


    parameters = {
        "active_page": "disk",
        "disks": disks,
        "pool": BACKEND.is_pool_configured,
        "imported_pools": imports,
        "csp_nonce": g.csp_nonce,
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
        verify['last'] = datetime.fromtimestamp(verify['last']).strftime("%c")

    parameters['verify'] = verify



    return render_template("disk_mngt.html", **parameters)

@bp.route('/disks/smart', methods=['POST'])
def smart_disk() -> str:
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        flash("CSRF validation failed","error")
        return redirect(url_for("main.advanced"))

    d = BACKEND.smart_info(request.form.get("disk"))

    return render_template("disk_smart.html", disk = d)


# ACTION PAGES

@bp.route('/disks/add', methods=['POST'])
def add_disk() -> Response:
    attachable_disks = BACKEND.attachable_disks
    form = AddDisksForm(attachable_disks)

    if (form.validate_on_submit()):
        try:
            task = expand_pool.delay(form.disks.data,str(get_locale()))
            BACKEND.append_task(NMSTask(task.task_id, "/disks", tag="add_disk"))
        except Exception as e:
            ...
    else:
        #TODO fix this how you fix the other(s)
        flash(f"Unable to process the form: {form.errors}","error")

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

        lang = str(get_locale())

        task = create_pool.delay(pool_name,dataset_name,redundancy,encryption,compression,disks, lang)
        BACKEND.append_task(NMSTask(task.task_id,"/disks",tag="new_disk"))

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
            if (form.key.data):

                key_data = form.key.data.read()

                BACKEND.import_tank_key(key_data)
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
    try:
        BACKEND.unmount()
    except Exception as e:
        flash(str(e),"error")
    else:
        flash("Disk array unmounted successfully","success")

    return redirect(url_for("main.disk_management"))


@bp.route("/disk/mount",methods=['POST'])
def mount() -> Response:
    try:
        BACKEND.mount()
    except Exception as e:
        flash(str(e), "error")
    else:
        flash("Disk array mounted successfully", "success")

    return redirect(url_for("main.disk_management"))

@bp.route("/disk/replace",methods=['POST'])
def replace_disk():
    try:
        validate_csrf(request.form.get("csrf_token"))
        disk = request.form.get("disk")

        if (disk is None):
            flash("Invalid disk to replace", "error")
        else:
            BACKEND.replace(disk)
    except ValidationError:
        flash("CSRF validation failed", "error")
    except Exception as e:
        flash(f"Unable to replace disk: {str(e)}", "error")


    return redirect(url_for("main.disk_management"))



# WAIT PAGES

@bp.route('/disks/new/wait')
def new_pool_wait() -> str:
    return render_template("wait.indeterminate.html",
                           active_page="disk",
                           refresh_to=url_for("main.disk_management"),
                           extra_css=["pacman.css"],
                           csp_nonce=g.csp_nonce,
                           hide_flash=True,
                           waiting_message=_("The creation of a new disk array may take some time. Please wait..."))

@bp.route('/disks/add/wait')
def add_disk_wait() -> Union[str,Response]:
    tasks = BACKEND.get_tasks
    add_disk_task = None

    for task in tasks:
        if task.tag == "add_disk":
            add_disk_task = task


    if add_disk_task is None:
        return redirect(url_for("main.disk_management"))

    return render_template("wait.determinate.html",
                           active_page="disk",
                           refresh_to=url_for("main.disk_management"),
                           task_id=add_disk_task.task_id,
                           csp_nonce=g.csp_nonce)

