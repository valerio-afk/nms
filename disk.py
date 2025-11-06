from dataclasses import dataclass
from enum import  Enum
import json

class DiskStatus(Enum):
    NEW       = 0
    ONLINE    = 1
    OFFLINE   = -1
    CORRUPTED = -2

    def __str__(this):
        match (this):
            case DiskStatus.NEW: return "New"
            case DiskStatus.ONLINE: return "Online"
            case DiskStatus.OFFLINE: return "Offline"
            case DiskStatus.CORRUPTED: return "Corrupted/Damaged"


@dataclass(frozen=True)
class Disk:
    name:str
    model:str
    serial:str
    size:int
    status:DiskStatus
    path:str

    def serialise(this):
        return {
            "model": this.model,
            "serial": this.serial,
        }

    def __eq__(this, other):
        if (isinstance(other,Disk)):
            return (other.model == this.model) and (other.serial == this.serial)