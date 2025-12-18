import datetime
import os
import pyotp
import qrcode
import time
from flask import render_template, redirect, url_for, jsonify, request, flash, Blueprint, g, send_file, session, abort
from io import BytesIO
from importlib import import_module
from flask_wtf.csrf import generate_csrf, validate_csrf
from wtforms import ValidationError

from constants import KEYPATH
from forms import CreatePoolForm, ImportPoolForm
from widget import render_widget,get_widgets_html,get_widgets_css_files
from backend import BACKEND, LogFilter
from tasks import create_pool, NMSTask, apt_get_updates, apt_get_upgrade
from decorators import wait

bp = Blueprint('main',__name__)

def widget_system_admin():

    return render_widget("sys_admin",encrypted=BACKEND.has_encryption)

def widget_system_updates():
    apt = {
        'csrf_token': generate_csrf(),
        'last_update' : BACKEND.last_apt_time(),
        'updates': BACKEND.get_updates,
        'state': None
    }

    if (apt['last_update'] is not None):
        apt['last_update'] = apt['last_update'].strftime("%c")

    celery_tasks = BACKEND.get_tasks_by_path("/advanced/apt")

    for t in celery_tasks:
        if (t.action is not None):
            apt['state'] = t.action

    return render_widget("apt", **apt)

def widget_danger_zone():

    return render_widget("danger_zone")

def widget_disk_usage():
    try:
        pool_capacity = BACKEND.get_pool_capacity
        used = pool_capacity['used']
        total = pool_capacity['total']
        capacity = int(used / total * 1000) / 10 if total > 0 else 0
    except Exception as e:
        flash(f"Error while retrieving disk array usage information: {str(e)}","error")
        used = 0
        total = 0
        capacity = 0



    return render_widget("disk_usage",used=used, total=total, capacity=capacity,mounted=BACKEND.is_mounted)



@bp.route('/async/widgets/apt')
def async_widget_system_updates():
    return widget_system_updates()[0]

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

    services = [(name.upper(),obj.is_active) for name,obj in access_services.items()]

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

@bp.route("/disk/unmount",methods=['POST'])
def unmount():
    try:
        BACKEND.unmount()
    except Exception as e:
        flash(str(e),"error")
    else:
        flash("Disk array unmounted successfully","success")

    return redirect(url_for("main.disk_management"))


@bp.route("/disk/mount",methods=['POST'])
def mount():
    try:
        BACKEND.mount()
    except Exception as e:
        flash(str(e), "error")
    else:
        flash("Disk array mounted successfully", "success")

    return redirect(url_for("main.disk_management"))


@bp.route('/disks/new',methods=['POST'])
@wait()
def new_pool():
    disks = BACKEND.get_disks()
    form = CreatePoolForm([d.path for d in disks])

    if (form.validate_on_submit()):
        redundancy = form.redundancy.data
        encryption = form.encryption.data
        compression = form.compression.data

        pool_name = form.pool_name.data
        dataset_name = form.dataset_name.data

        disks = form.disks.data

        task = create_pool.delay(pool_name,dataset_name,redundancy,encryption,compression,disks)
        BACKEND.append_task(NMSTask(task.task_id,"/disks"))

    else:
        flash("Form validation failed.","error")

    return redirect(url_for("main.disk_management"))

@bp.route('/disk/import/<string:pool>',methods=['POST'])
def import_pool(pool):
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




@bp.route('/disks')
@wait(redirect_to="/disks/new/wait")
def disk_management():
    disks = BACKEND.get_disks()
    pool = BACKEND.is_pool_configured()

    importable_pools = BACKEND.get_importable_pools()
    imports = [
        (p['name'],p['disks'], p['message'] if p['state']!="ONLINE" else None , ImportPoolForm()) for p in importable_pools
    ]

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
                           imported_pools=imports,
                           verify=verify,
                           scrub = scrub_report,
                           mounted=BACKEND.is_mounted,
                           new_pool_form = CreatePoolForm([d.path for d in disks]),
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

    return jsonify([t.id for t in tasks])


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
    try:
        serv = BACKEND.get_access_services.get(service,None)

        if (serv is None):
            flash(f"Service `{service}` not recognised","error")
            return redirect(url_for("main.access"))

        forms = import_module("forms")
        service_form_cls = getattr(forms, f"{service.upper()}ServiceForm")
        service_enabled = serv.is_active
        form = service_form_cls(enabled=service_enabled)

        if (form.validate_on_submit()):
            form_action = request.form.get('action')
            form_data = {k:v.data for k,v in form._fields.items()}
            getattr(serv,form_action)(**form_data)

            match(form_action):
                case "enable":
                    flash(f"Service { service.upper() } enabled successfully.","success")
                case "update":
                    flash(f"Service {service.upper()} settings updated successfully.", "success")
                case "disable":
                    flash(f"Service {service.upper()} disabled successfully.", "success")


        elif (request.method == 'POST'):
            for field, errors in form.errors.items():
                for error in errors:
                    flash(str(error), "error")
    except Exception as e:
        flash(str(e),"error")

    return redirect(url_for("main.access"))


@bp.route("/access")
def access():
    forms = import_module("forms")
    widgets = []
    mountpoint  = BACKEND.mountpoint

    if (not BACKEND.is_pool_configured()):
        flash("You need to configure your disk array before enabling any access services","error")

    for k,v in BACKEND.get_access_services.items():
        service_form_cls = getattr(forms,f"{k.upper()}ServiceForm")
        service_enabled = v.is_active
        form = service_form_cls(enabled=service_enabled)


        for prop in v.properties:
            try:
                attr = getattr(form,prop)
                attr.default = v.get(prop)
            except AttributeError:
                ...

        form.process()

        ip_range = request.remote_addr.split(".")
        if (len(ip_range)==4):
            ip_range = f"{ip_range[0]}.{ip_range[2]}.{ip_range[3]}.0/24"

        if (ip_range is None):
            ip_range = "*"

        widget = render_widget(f"access.{k}",enabled=service_enabled,form=form,mountpoint=mountpoint,ip=request.remote_addr,ip_range=ip_range)
        widgets.append(widget[0])

    return render_template("access.html",active_page="access",services=widgets,csp_nonce=g.csp_nonce)

@bp.route("/advanced")
def advanced():

    dashboard_widgets = [
        widget_system_admin(),
        widget_system_updates()
    ]

    if BACKEND.is_pool_configured():
        dashboard_widgets.append(widget_danger_zone())

    return render_template("advanced.html",
                           csp_nonce=g.csp_nonce,
                           widgets=get_widgets_html(dashboard_widgets),
                           extra_css=get_widgets_css_files(dashboard_widgets),
                           active_page="advanced"
                           )

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
        raise Exception("CSRF validation failed")
        abort(400)

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
                flash(f"Invalid authorisation", "error")

        else:
            flash("Authorisation token expired","error")

        return redirect(url_for("main.advanced"))


@bp.route("/login",methods=['GET','POST'])
def login():
    authenticated = False
    if (BACKEND.is_otp_configured):

        if (request.method == 'POST'):
            try:
                validate_csrf(request.form.get("csrf_token"))
            except ValidationError:
                raise Exception("CSRF validation failed")
                abort(400)

            otp = request.form.get("otp")

            BACKEND.logger.info(f"Login request. OTP: {otp}")

            if (BACKEND.verify_otp(otp)):
                session["authenticated"] = True
                session["login_time"] = time.time()
                session["last_activity"] = time.time()
                session["ip"] = request.remote_addr
                authenticated = True
                BACKEND.logger.info(f"OTP accepted")
            else:
                BACKEND.logger.warning(f"Invalid OTP")

        elif session.get("authenticated",False):
            authenticated = True

        if authenticated:
            return redirect(url_for("main.dashboard"))

        return render_template("login.auth.html",csp_nonce=g.csp_nonce,csrf_token= generate_csrf())
    else:
        return redirect(url_for("main.configure_otp"))

@bp.route("/login/reauth/<string:operation>",methods=['GET','POST'])
def reauth  (operation):

    if (BACKEND.is_otp_configured):

        if (request.method == 'POST'):
            try:
                validate_csrf(request.form.get("csrf_token"))
            except ValidationError:
                raise Exception("CSRF validation failed")
                abort(400)

            otp = request.form.get("otp")

            BACKEND.logger.info(f"Login request. OTP: {otp}")

            if (BACKEND.verify_otp(otp)):
                session["dz_authorisation"] = {"time":time.time(),"timestamp":time.time(),"operation":operation}
                BACKEND.logger.info(f"OTP accepted")
                flash("OTP Accepted. Please press again the button of the desired dangerous operation to continue.",
                      "success")
            else:
                BACKEND.logger.warning(f"Invalid OTP")
                flash("Invalid OTP","error")



            return redirect(url_for("main.advanced"))

        return render_template("login.reauth.html",csp_nonce=g.csp_nonce,csrf_token= generate_csrf())
    else:
        return redirect(url_for("main.configure_otp"))

@bp.route("/login/config",methods=['GET','POST'])
def configure_otp():

    if (BACKEND.is_otp_configured):
        return redirect(url_for("main.login"))

    if (request.method == 'POST'):
        secret = session.get("pending_otp_secret")
        if secret is not None:
            del session['pending_otp_secret']
            BACKEND.set_otp_secret(secret)
            return redirect(url_for("main.login"))


    secret = pyotp.random_base32()
    session['pending_otp_secret'] = secret

    return render_template("login.otp.html",csrf_token= generate_csrf())

@bp.route("/login/config/show_qrcode")
def otp_qr():
    secret = session.get("pending_otp_secret")
    if not secret:
        return "Setup not started", 400

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(
        issuer_name="NMS"
    )

    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@bp.route("/logout",methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for("main.login"))

@bp.route('/advanced/apt',methods=['POST'])
@wait()
def apt_get():

    action = request.form.get("action",None)

    if (action=="update"):
        task = apt_get_updates.delay()
        BACKEND.append_task(NMSTask(task.task_id,"/advanced/apt",action=action))
    elif (action == "upgrade"):
        task = apt_get_upgrade.delay()
        BACKEND.append_task(NMSTask(task.task_id, "/advanced/apt", action=action))
    return redirect(url_for("main.advanced"))

@bp.before_request
def check_flash_messages_from_tasks():
    tasks = BACKEND.pop_completed_tasks()

    reload_config = False

    for t in tasks:
        flash(t.result,"success" if t.successful else "error")
        reload_config = True


    if (reload_config):
        BACKEND.load_configuration_file()

@bp.before_request
def require_login():
    last_activity = session.get("last_activity",None)

    if (last_activity is not None):
        current_time = time.time()
        if ((current_time - last_activity) > (60*30)):
            session.clear()
        else:
            session["last_activity"] = current_time

    if request.endpoint not in ("main.login", "static","main.configure_otp","main.otp_qr"):
        if session.get("authenticated",False) is not True:
            return redirect(url_for("main.login"))


@bp.after_request
def scrub_checker(response):

    BACKEND.check_scrub_status()
    return response

@bp.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
