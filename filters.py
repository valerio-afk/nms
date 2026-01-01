from typing import Optional

from markdown import markdown
from disk import DiskStatus
from flask_babel import _

def disk_charm(disk_status:DiskStatus):
    match (disk_status):
        case DiskStatus.NEW: return "✴️"
        case DiskStatus.ONLINE: return "🟢"
        case DiskStatus.OFFLINE: return "🔴"
        case DiskStatus.CORRUPTED: return "⚠️"

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