from nms_shared.disks import Disk

from typing import List


class ConfigMixin:
    def get_configured_disks(this) -> List[Disk]:
       ...
