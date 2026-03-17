from markdown import markdown
from typing import Optional
from flask_babel import _
from nms_shared.enums import DiskStatus

def disk_charm(disk_status:DiskStatus) -> str:
    match (disk_status):
        case DiskStatus.NEW: return "✴️"
        case DiskStatus.ONLINE: return "🟢"
        case DiskStatus.OFFLINE: return "🔴"
        case DiskStatus.CORRUPTED: return "⚠️"

def iface_charm(iface_type:str) -> str:
    match (iface_type):
        case "ethernet": return "🔌️"
        case "wifi": return "🛜"
        case _: return ""

def disk_status_babel(disk_status:DiskStatus):
    match (disk_status):
        case DiskStatus.NEW: return _("New")
        case DiskStatus.ONLINE: return _("Online")
        case DiskStatus.OFFLINE: return _("Offline")
        case DiskStatus.CORRUPTED: return _("Corrupted")

def enabled_fmt(status:bool):
    fmt = _("Enabled") if status else _("Disabled")
    badge = "success" if status else "danger"
    return f'<span class="badge bg-{badge}">{fmt}</span>'

def boolean_fmt(status:bool):
    fmt = _("Yes") if status else _("No")
    badge = "success" if status else "danger"
    return f'<span class="badge bg-{badge}">{fmt}</span>'

def human_readable_bytes(bytes:Optional[int]) -> str:

    if (bytes is None):
        return ""

    magnitutes = ["B", "KB", "MB", "GB", "TB"]

    i = 0

    while ( (bytes>=1024) and (i<len(magnitutes)) ):
        bytes /= 1024
        i+=1

    return f"{bytes:.2f}{magnitutes[i]}"

def markdown_filter(s):
    return markdown(s,extensions=["extra"])

def smart_label(lbl:str)->str:
    match (lbl):
        case "dev_reference":
            return _("Device")
        case "is_ssd":
            return _("Is SSD")
        case "dev_interface":
            return _("Interface")
        case _:
            return _(lbl.replace("_", " ").title())