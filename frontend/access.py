from . import frontend as bp, BACKEND
from importlib import import_module
from flask import render_template, request, flash, redirect, url_for, Response, g
from widget import render_widget
from flask_babel import get_locale

# MAIN PAGE

@bp.route("/access")
def access() -> str:
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

# ACTION PAGES

@bp.route("/access/update/<string:service>",methods=['POST'])
def change_access_settings(service) -> Response:
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