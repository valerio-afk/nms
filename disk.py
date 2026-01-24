from flask_babel import _
from typing import Optional

from nms_shared.enums import DiskStatus

class DiskStatusMixin:
    def __str__(this) -> Optional[str]:
        match (this):
            case FrontEndDiskStatus.NEW: return _("New")
            case FrontEndDiskStatus.ONLINE: return _("Online")
            case FrontEndDiskStatus.OFFLINE: return _("Offline")
            case FrontEndDiskStatus.CORRUPTED: return _("Corrupted")
            case _: return None

class FrontEndDiskStatus(DiskStatusMixin,DiskStatus):
    ...





