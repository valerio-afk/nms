from . import frontend as bp, NMSBACKEND as BACKEND
from flask import render_template, g, redirect, url_for, Response

from .utils.forms import IFaceEnableForm
from .utils.widget import render_widget


@bp.route("/network")
def network() -> str:

    widgets = []

    for iface in BACKEND.network_interfaces:
        enabler_form = IFaceEnableForm(iface_enabler=iface['enabled'])

        widget,css = render_widget("iface",enabler_form=enabler_form,iface=iface)
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


    # forms =  import_module("frontend.utils.forms")
    # widgets = []
    # mountpoint  = BACKEND.mountpoint
    #
    # if (not BACKEND.is_pool_configured):
    #     show_flash(type="warning",code=WarningMessages.W_POOL_NEEDED.name)
    #
    # for k,v in BACKEND.access_services.items():
    #     service_form_cls = getattr(forms,f"{k.upper()}ServiceForm")
    #     service_enabled = v['active']
    #     form = service_form_cls(enabled=service_enabled)
    #
    #
    #     for prop in v['properties']:
    #         try:
    #             attr = getattr(form,prop)
    #             attr.default = v['properties'][prop]
    #         except AttributeError:
    #             ...
    #
    #     form.process()
    #
    #     ip_range = request.remote_addr.split(".")
    #     if (len(ip_range)==4):
    #         ip_range = f"{ip_range[0]}.{ip_range[2]}.{ip_range[3]}.0/24"
    #
    #     if (ip_range is None):
    #         ip_range = "*"
    #
    #     widget = render_widget(f"access.{k}",enabled=service_enabled,form=form,mountpoint=mountpoint,ip=request.remote_addr,ip_range=ip_range)
    #     widgets.append(widget[0])


