from flask_wtf.csrf import validate_csrf

from . import frontend as bp, NMSBACKEND as BACKEND
from flask import render_template,  redirect, url_for, Response, request
from nms_shared import ErrorMessages
from .api.backend_proxy import show_flash
from .utils.forms import IFaceEnableForm, IPEnableForm, IPForm
from .utils.widget import render_widget
from wtforms import ValidationError

@bp.route("/network")
def network() -> str:

    widgets = []

    for iface in BACKEND.network_interfaces:
        enabler_form = IFaceEnableForm(iface_enabler=iface['enabled'])

        ip_forms = {k:None for k in sorted([x for x in iface.keys() if x.startswith("ip")])}


        for ip in ip_forms.keys():
            ip_details = iface[ip]

            version = ip[:2].upper() + ip[2:]

            if ("enabled" in ip_details.keys()):
                ip_form = IPEnableForm(version=version)
            else:
                ip_form = IPForm(version=version)

            for (k,v) in ip_details.items():
                if (hasattr(ip_form, k)):
                    field = getattr(ip_form, k)
                    field.data = v

            ip_forms[ip] = ip_form



        widget,css = render_widget("iface",enabler_form=enabler_form,ip_forms=ip_forms,iface=iface)
        widgets.append(widget)

    return render_template("network.html",
                           active_page="network",
                           ifaces=widgets)


@bp.route("/network/<string:iface>/<string:action>",methods=["POST"])
def iface_change_status(iface:str, action:str) -> Response:
    match (action.lower()):
        case "up":
            BACKEND.iface_up(iface)
        case "down":
            BACKEND.iface_down(iface)

    return redirect(url_for("main.network"))

@bp.route("/network/<string:iface>/config", methods=["POST"])
def iface_change_conf(iface:str) -> Response:
    profile = request.args.get("profile")

    if (profile):

        ip_version = request.form.get("version","").lower()

        form = IPEnableForm() if "6" in ip_version else IPForm()

        if (form.validate_on_submit()):
            settings = {
                "dynamic": form.dynamic.data,
                "address": form.address.data,
                "netmask": form.netmask.data,
                "gateway": form.gateway.data,
                "dns": form.dns.data,
            }

            if (isinstance(form, IPEnableForm)):
                settings["enabled"] = form.enabled.data

            BACKEND.iface_setup(iface, ip_version, profile, settings)

        else:
            show_flash(code=ErrorMessages.E_CSRF.name)



    return redirect(url_for("main.network"))