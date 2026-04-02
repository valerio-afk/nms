from markdown import markdown
from typing import Optional, Union
from flask_babel import _
from pytz import tzinfo

from nms_shared.enums import DiskStatus
from datetime import datetime,timedelta, timezone
from flask_babel import format_datetime

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

def notification_date_format(ts:Union[int,str])->str:

    if (isinstance(ts,str)):
        now = datetime.now()
        ts_datetime = datetime.fromisoformat(ts)
        ts_date = ts_datetime.date()
    else:
        now = datetime.now()
        ts_datetime = datetime.fromtimestamp(ts)
        ts_date = ts_datetime.date()


    today = now.date()
    yesterday = today - timedelta(days=1)

    time = format_datetime(ts_datetime, "HH:mm:ss",rebase=False)

    if ts_date == today:
        return time
    elif ts_date == yesterday:
        return f"{_("Yesterday")} {time}"
    else:
        return f"{format_datetime(ts_datetime, "dd/MM/yyyy",rebase=False)} {time}"