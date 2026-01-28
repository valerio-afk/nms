from nms_shared.disks import Disk
from typing import List

class DiskMixin:

    @staticmethod
    def get_system_disks() -> List[Disk]:
        ...

    def get_disks(this) -> List[Disk]:
        ...

    def _format_disk(this,device:str)-> None:
        ...


    def format_disk(this,device:str)->None:
        ...


    def smart_info(this, device:str)->dict:
        ...