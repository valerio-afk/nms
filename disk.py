from dataclasses import dataclass
from enum import  Enum
from typing import Optional, List, Dict, Union, Any, Iterable
import subprocess

class DiskStatus(Enum):
    NEW       = 0
    ONLINE    = 1
    OFFLINE   = -1
    CORRUPTED = -2

    def __str__(this) -> str:
        match (this):
            case DiskStatus.NEW: return "New"
            case DiskStatus.ONLINE: return "Online"
            case DiskStatus.OFFLINE: return "Offline"
            case DiskStatus.CORRUPTED: return "Corrupted/Damaged"

@dataclass
class Disk:
    name:str
    model:str
    serial:str
    size:int
    status:Optional[DiskStatus]
    path:str

    def serialise(this) -> Dict[str, Union[str,Iterable[str]]]:
        return {
            "name":this.name,
            "model": this.model,
            "serial": this.serial,
            "size": this.size,
            "path": this.path,
            "physical_paths": this.physical_paths,
        }

    def __eq__(this, other:Any) -> bool:
        if (isinstance(other,Disk)):
            return other.serial == this.serial
        return False

    def __hash__(this) -> int:
        return hash(this.serial)

    def has_path(this,path:str) -> bool:
        paths = this.physical_paths
        paths.append(this.path)

        return path in paths

    def has_any_paths(this,paths:List[str]) -> bool:

        return any([this.has_path(p) for p in paths])

    @property
    def physical_paths(this) -> List[str]:
        try:
            result = subprocess.run(
                ["udevadm", "info", "--query=symlink", f"--name={this.path}"],
                capture_output=True,
                text=True,
                check=True,
            )
            symlinks = result.stdout.split()
            return sorted(["/dev/" + s for s in symlinks if s.startswith("disk/by-path/")])
        except subprocess.CalledProcessError:
            return []

