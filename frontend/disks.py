from . import frontend as bp, BACKEND, NMSTask
from .tasks import  expand_pool, create_pool
from datetime import datetime
from flask import g, render_template, redirect, url_for, flash, Response
from forms import ImportPoolForm, CreatePoolForm, AddDisksForm
from frontend.decorators import wait
from typing import Union



# MAIN PAGE

@bp.route('/disks')
@wait(redirect_to="/disks/new/wait",tag="new_disk")
@wait(redirect_to="/disks/add/wait",tag="add_disk")
def disk_management() -> str:
    disks = BACKEND.get_disks()
    attachable_disks = BACKEND.get_attachable_disks

    importable_pools = BACKEND.get_importable_pools()
    imports = [
        (p['name'],p['disks'], p['message'] if p['state']!="ONLINE" else None , ImportPoolForm()) for p in importable_pools
    ]

    parameters = {
        "active_page": "disk",
        "disks": disks,
        "pool": BACKEND.is_pool_configured(),
        "imports": imports,
        "csp_nonce": g.csp_nonce,
    }


    if (parameters['pool'] == False):
        parameters['new_pool_form'] = CreatePoolForm(disks)
    else:
        parameters['mounted'] = BACKEND.is_mounted
        parameters['scrub'] = BACKEND.get_last_scrub_report()
        parameters["attachable_disks"] = None if len(attachable_disks) == 0 else AddDisksForm(attachable_disks)

    verify = BACKEND.get_scrub_info

    if (verify['last'] is None):
        verify['last'] = "Never"
    else:
        verify['last'] = datetime.fromtimestamp(verify['last']).strftime("%c")

    parameters['verify'] = verify



    return render_template("disk_mngt.html", **parameters)


# ACTION PAGES

@bp.route('/disks/add', methods=['POST'])
def add_disk() -> Response:
    attachable_disks = BACKEND.get_attachable_disks
    form = AddDisksForm(attachable_disks)

    if (form.validate_on_submit()):
        try:
            task = expand_pool.delay(form.disks.data)
            BACKEND.append_task(NMSTask(task.task_id, "/disks", tag="add_disk"))

            flash(f"Adding {form.disks.data} to your pool. This operation can take long")
        except Exception as e:
            flash(f"Error while adding {form.disks.data}: {str(e)}"
                  , "error")
    else:
        flash(f"Unable to process the form: {form.errors}","error")

    return redirect(url_for("main.disk_management"))

@bp.route('/disks/new',methods=['POST'])
@wait()
def new_pool() -> Response:
    disks = BACKEND.get_disks()
    form = CreatePoolForm(disks)

    if (form.validate_on_submit()):
        redundancy = form.redundancy.data
        encryption = form.encryption.data
        compression = form.compression.data

        pool_name = form.pool_name.data
        dataset_name = form.dataset_name.data

        disks = form.disks.data

        task = create_pool.delay(pool_name,dataset_name,redundancy,encryption,compression,disks)
        BACKEND.append_task(NMSTask(task.task_id,"/disks",tag="new_disk"))

    else:
        flash(f"Form validation failed: {form.errors}","error")

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


# WAIT PAGES

@bp.route('/disks/new/wait')
def new_pool_wait() -> str:
    return render_template("wait.indeterminate.html",
                           active_page="disk",
                           refresh_to=url_for("main.disk_management"),
                           extra_css=["pacman.css"],
                           csp_nonce=g.csp_nonce,
                           waiting_message="The creation of a new disk array may take some time. Please wait...")

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