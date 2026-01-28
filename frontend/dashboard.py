from . import frontend as bp, NMSBACKEND as BACKEND
from flask import  render_template, g, flash
from typing import Optional, Tuple
from widget import render_widget, get_widgets_css_files, get_widgets_html


def widget_disk_overview() -> Tuple[str,Optional[str]]:
    disks = BACKEND.get_disks()
    pool_options = BACKEND.get_pool_options if BACKEND.is_pool_configured else []


    return render_widget("disk_list",disks=disks,pool_options=pool_options)

def widget_sys_info() -> Tuple[str,Optional[str]]:
    sys_info = BACKEND.system_information

    return render_widget("system_info",system_info=sys_info)

def widget_network_overview() -> Tuple[str,Optional[str]]:
    ifaces = BACKEND.iface_status()
    return render_widget("network_list",ifaces=ifaces)

def widget_access_overview() -> Tuple[str,Optional[str]]:
    access_services = BACKEND.access_services

    services = [(name.upper(),obj.get('active')) for name,obj in access_services.items()]

    return render_widget("access_list",services=services)

def widget_disk_usage() -> Tuple[str,Optional[str]]:
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

@bp.route('/async/widgets/network_overview')
def async_widget_network_overview() -> str:
    return widget_network_overview()[0]

@bp.route('/async/widgets/disk_overview')
def async_widget_disk_overview() -> str:
    return widget_disk_overview()[0]

@bp.route('/async/widgets/system_info')
def async_widget_sys_info() -> str:
    return widget_sys_info()[0]

@bp.route('/async/widgets/disk_usage')
def async_widget_disk_usage() -> str:
    return widget_disk_usage()[0]


@bp.route('/')
def dashboard() -> str:
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