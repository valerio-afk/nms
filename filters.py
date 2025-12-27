from typing import Optional

from markdown import markdown
from disk import DiskStatus

def disk_charm(disk_status:DiskStatus):
    match (disk_status):
        case DiskStatus.NEW: return "✴️"
        case DiskStatus.ONLINE: return "🟢"
        case DiskStatus.OFFLINE: return "🔴"
        case DiskStatus.CORRUPTED: return "⚫"

def enabled_fmt(status:bool):
    fmt = "Enabled" if status else "Disabled"
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