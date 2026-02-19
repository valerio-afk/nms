from . import frontend as bp, NMSBACKEND as BACKEND
from importlib import import_module
from flask import render_template, request, flash, redirect, url_for, Response, g
from frontend.utils.widget import render_widget
from nms_shared.msg import ErrorMessages, WarningMessages
from .api.backend_proxy import  show_flash


# MAIN PAGE

@bp.route("/access")
def access() -> str:
    forms =  import_module("frontend.utils.forms")
    widgets = []
    mountpoint  = BACKEND.mountpoint

    if (not BACKEND.is_pool_configured):
        show_flash(type="warning",code=WarningMessages.W_POOL_NEEDED.name)

    for k,v in BACKEND.access_services.items():
        service_form_cls = getattr(forms,f"{k.upper()}ServiceForm")
        service_enabled = v['active']
        form = service_form_cls(enabled=service_enabled)


        for prop in v['properties']:
            try:
                attr = getattr(form,prop)
                attr.default = v['properties'][prop]
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
        serv = BACKEND.access_services.get(service)

        if (serv is None):
            show_flash(code=ErrorMessages.E_ACCESS_SERV_UNK.name,params=[service.upper()])
            return redirect(url_for("main.access"))

        forms = import_module("frontend.utils.forms")
        service_form_cls = getattr(forms, f"{service.upper()}ServiceForm")
        service_enabled = serv['active']
        form = service_form_cls(enabled=service_enabled)
        form_action = request.form.get('action')

        if (form.validate_on_submit()) or (form_action=="disable"):
            form_data = {k:v.data for k,v in form._fields.items() if k not in ["action","csrf_token"]}

            match (form_action):
                case "enable":
                    BACKEND.enable_service(service, **form_data)
                case "disable":
                    BACKEND.disable_service(service, **form_data)
                case "update":
                    BACKEND.update_service(service, **form_data)


        elif (request.method == 'POST'):
            for field, errors in form.errors.items():
                for error in errors:
                    flash(str(error), "error")
    except Exception as e:
        flash(str(e),"error")

    return redirect(url_for("main.access"))
