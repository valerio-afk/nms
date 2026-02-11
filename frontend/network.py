from . import frontend as bp, NMSBACKEND as BACKEND
from .api.backend_proxy import show_flash
from .utils.forms import IFaceEnableForm, IPEnableForm, IPForm
from .utils.widget import render_widget
from flask import render_template,  redirect, url_for, Response, request, g
from flask_wtf.csrf import validate_csrf, generate_csrf, ValidationError
from nms_shared import ErrorMessages



@bp.route("/network")
def network() -> str:

    widgets = []

    for iface in BACKEND.network_interfaces:
        enabler_form = IFaceEnableForm(iface_enabler=iface['enabled']) if ((iface.get("type")=="ethernet") or iface.get('has_profile') == True) else None

        ip_forms = {k:None for k in sorted([x for x in iface.keys() if x.startswith("ip")])}


        for ip in ip_forms.keys():
            ip_details = iface[ip]

            if (ip_details is not None):
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

        ip_forms = {k:v for (k,v) in ip_forms.items() if v is not None}

        widget,css = render_widget("iface",enabler_form=enabler_form,ip_forms=ip_forms,iface=iface)
        widgets.append(widget)

    return render_template("network.html",
                           active_page="network",
                           ifaces=widgets,
                           csp_nonce=g.csp_nonce)


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

@bp.route("/network/<string:iface>/wifi", methods=["POST"])
def wifi_connect(iface:str) -> Response:

    try:
        validate_csrf(request.form.get("csrf_token"))

        form = request.form

        ifaces = BACKEND.network_interfaces
        profile_name = None

        for x in ifaces:
            if (x['name']== iface):
                if (x['has_profile']):
                    profile_name = x['network_name']

        ssid = form.get("selected_network")

        if (ssid is not None):
            if (ssid == "hidden"):
                ssid = form.get("custom-ssid")

            psk = form.get("psk")

            BACKEND.wifi_connect(iface,ssid, psk, profile_name)

    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)

    return redirect(url_for("main.network"))


@bp.route("/network/<string:iface>/list",methods=["GET"])
def async_wifi_list(iface:str) -> str:
    networks = BACKEND.wifi_list(iface)
    return render_template("wifi_network_list.html",networks=networks,iface=iface,csrf_token=generate_csrf())


@bp.route("/network/<string:iface>/<string:action>",methods=["POST"])
def iface_change_status(iface:str, action:str) -> Response:
    match (action.lower()):
        case "up":
            BACKEND.iface_up(iface)
        case "down":
            BACKEND.iface_down(iface)

    return redirect(url_for("main.network"))

