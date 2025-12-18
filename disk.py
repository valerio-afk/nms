from dataclasses import dataclass
from enum import  Enum
import subprocess

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
            "path": this.path,
            "physical_path": this.physical_path,
        }

    def __eq__(this, other):
        if (isinstance(other,Disk)):
            return (other.model == this.model) and (other.serial == this.serial)

    @property
    def physical_path(this):
        try:
            result = subprocess.run(
                ["udevadm", "info", "--query=symlink", f"--name={this.path}"],
                capture_output=True,
                text=True,
                check=True,
            )
            symlinks = result.stdout.split()
            return ["/dev/" + s for s in symlinks if s.startswith("disk/by-path/")]
        except subprocess.CalledProcessError:
            return []