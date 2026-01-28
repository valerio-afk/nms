from flask_babel import _
from nms_shared.enums import DiskStatus
from typing import Optional

def get_disk_status_label(d:DiskStatus) -> Optional[str]:
    match (d):
        case DiskStatus.NEW: return _("New")
        case DiskStatus.ONLINE: return _("Online")
        case DiskStatus.OFFLINE: return _("Offline")
        case DiskStatus.CORRUPTED: return _("Corrupted")







