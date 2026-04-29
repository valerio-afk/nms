from . import frontend as bp, NMSBACKEND as BACKEND
from .api.backend_proxy import show_flash
from .utils.forms import IFaceEnableForm, IPEnableForm, IPForm, VPNForm
from .utils.widget import render_widget
from enum import Enum
from flask import render_template,  redirect, url_for, Response, request, g, send_file
from flask_babel import format_datetime
from flask_wtf.csrf import validate_csrf, generate_csrf, ValidationError
from io import BytesIO
from nms_shared import ErrorMessages
import base64
import datetime

class DDNSProviders(Enum):
    noip = "No-IP"
    duckdns = "DuckDNS"
    dynu = "Dynu"
    freedns = "FreeDNS"
    dnsexit = "DNSExit"
    dynv6 = "DynV6"
    cloudns = "ClouDNS"

def get_vpn_public_key() -> Response:
    key = BACKEND.vpn_public_key

    if (key is None):
        show_flash(code=ErrorMessages.E_NET_VPN_KEY.name)
        return redirect(url_for("main.advanced"))

    raw_data = base64.b64decode(key)
    key_fname = f"{BACKEND.dataset_name}.key"

    return send_file(BytesIO(raw_data),as_attachment=True,download_name=key_fname,mimetype="application/octet-stream")

@bp.route("/network")
def network() -> str:

    widgets = []

    for iface in BACKEND.network_interfaces:
        enabler_form = IFaceEnableForm(iface_enabler=iface['enabled'])

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

        ap = BACKEND.ap_config if (iface.get("type") == "wifi") else None

        if ((ap is not None) and (ap.get("iface") != iface.get("name"))):
            ap = None

        widget,css = render_widget("iface",enabler_form=enabler_form,ip_forms=ip_forms,iface=iface,ap=ap)
        widgets.append(widget)

    # vpn is special
    vpn_config = BACKEND.vpn_config
    vpn_enabled = vpn_config.get("enabled")

    vpn = {"enabled":vpn_enabled}
    vpn_enabler_form = IFaceEnableForm(iface_enabler=vpn_enabled)

    if (vpn_enabled):
        vpn_data = BACKEND.vpn_config
        vpn_form = VPNForm(
            address=vpn_data.get("ipv4",[]).get("address"),
            netmask=vpn_data.get("ipv4",[]).get("netmask"),
            public_ip = BACKEND.vpn_public_ip,
        )
        vpn['form'] = vpn_form

    vpn_widget,_ = render_widget("vpn", vpn=vpn, enabler_form=vpn_enabler_form, peers=BACKEND.vpn_get_peers)
    widgets.append(vpn_widget)

    #ddns is also special
    ddns_providers = BACKEND.ddns_providers
    if (ddns_providers is not None):
        for k in ddns_providers.keys():
            ddns_providers[k]['ui_name'] = DDNSProviders[k].value
            if (ddns_providers[k].get("last_update") is not None):
                ddns_providers[k]['last_update'] = format_datetime(datetime.datetime.fromtimestamp(ddns_providers[k]['last_update']),"EEEE, d MMMM yyyy HH:mm:ss").title()

            if (ddns_providers[k].get("next_update") is not None):
                ddns_providers[k]['next_update'] = format_datetime(datetime.datetime.fromtimestamp(ddns_providers[k]['next_update']), "EEEE, d MMMM yyyy HH:mm:ss").title()

    ddns_widget,_ = render_widget("ddns",ddns_providers=ddns_providers)
    widgets.append(ddns_widget)

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

@bp.route("/network/vpn/<string:action>",methods=["POST"])
def vpn_change_status(action:str) -> Response:
    match (action.lower()):
        case "up":
            BACKEND.iface_up("vpn")
        case "down":
            BACKEND.iface_down("vpn")

    return redirect(url_for("main.network"))

@bp.route("/network/<string:iface>/hotspot",methods=["POST"])
def enable_hotspot(iface:str) -> Response:
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:
        ssid = request.form.get("ssid")
        psk = request.form.get("psk")

        if (len(psk) == 0):
            psk = None

        BACKEND.enable_hotspot(iface,ssid, psk)

    return redirect(url_for("main.network"))

@bp.route("/network/<string:iface>/<string:action>",methods=["POST"])
def iface_change_status(iface:str, action:str) -> Response:
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:
        match (action.lower()):
            case "up":
                BACKEND.iface_up(iface)
            case "down":
                BACKEND.iface_down(iface)

    return redirect(url_for("main.network"))


@bp.route("/network/vpn/config",methods=['POST'])
def net_vpn_apply_changes() -> Response:
    form = request.form

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:
        match (form.get("action").lower()):
            case "get-pubkey":
                return get_vpn_public_key()
            case "genkeys":
                BACKEND.vpn_gen_keys()
            case "changes":
                BACKEND.vpn_change_config(
                    address=form['address'],
                    netmask=form['netmask'],
                    endpoint=form['public_ip'],
                )


    return redirect(url_for("main.network"))

@bp.route("/network/vpn/peers",methods=['POST'])
def vpn_peers() -> Response:
    form = request.form

    try:
        validate_csrf(form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:
        if ((peer:=form.get("remove")) is not None):
            BACKEND.vpn_remove_peer(peer)
        elif form.get("new") is not None:
            name = form.get("peer_name")
            public_key = form.get("public_key")
            BACKEND.vpn_add_peer(name, public_key)
    return redirect(url_for("main.network"))

@bp.route("/network/ddns/<string:provider>", methods=['POST'])
def ddns_conf(provider:str) -> Response:
    form = request.form

    try:
        validate_csrf(form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:
        if form.get("action") == "enable":
            username = form.get("username")
            password = form.get("password")

            if (isinstance(username,str) and (len(username) == 0)): username = None
            if (isinstance(password, str) and (len(password) == 0)): password = None

            BACKEND.ddns_enable(provider,{"username":username,"password":password})
        elif form.get("action") == "disable":
            BACKEND.ddns_disable(provider)

    return redirect(url_for("main.network"))