from datetime import timedelta
from typing import Tuple, Optional, List, Dict
from nms_shared.disks import Disk


class PoolMixin:

    @property
    def pool_name(this) -> str:
        ...

    @property
    def has_redundancy(this) -> bool:
        ...

    @property
    def has_encryption(this) -> bool:
        ...

    @property
    def has_compression(this) -> bool:
        ...

    @property
    def key_filename(this) -> str:
        ...


    @property
    def get_pool_capacity(this) -> Dict[str, int]:
        ...

    @property
    def get_array_expansion_status(this) -> Tuple[Optional[float], Optional[timedelta], bool]:
        ...

    @property
    def get_attachable_disks(this) -> List[Disk]:
        ...

    def get_pool_disks(this) -> List[Disk]:
        ...

    def get_pool_options(this) -> List[Tuple[str,bool]]:
        ...
        # return [
        #     (_("Redundancy"), this.has_redundancy),
        #     (_("Encryption"), this.has_encryption),
        #     (_("Compression"), this.has_compression),
        # ]

    def is_pool_configured(this) -> bool:
        ...

    def is_pool_present(this) -> bool:
        ...

    def destroy_tank(this) -> None:
        ...

    def get_importable_pools(this) -> dict:
        ...

    def create_pool(this,
                    poolname:str,
                    datasetname:str,
                    redundancy:bool,
                    encryption:bool,
                    compression:bool,
                    disks:list) -> None:

        ...

    def get_tank_key(this) -> bytes:
       ...

    def import_tank_key(this, handle) -> None:
        ...


    def import_pool(this,poolname,load_key:bool=False) -> None:
        ...

    def expand_pool(this,new_device:str) -> None:
        ...
        # cmd = None
        #
        # disks = this.get_attachable_disks
        #
        # new_disk_obj = [ d for d in disks if d.has_path(new_device)]
        #
        # if (len(new_disk_obj)!=1):
        #     raise Exception(ErrorMessage.get_error(ErrorMessage.E_POOL_EXPAND_INFO, new_device))
        #
        # new_disk_obj = new_disk_obj.pop()
        #
        # this.disable_all_access_services()
        # this.unmount()
        #
        # if this.has_redundancy:
        #     status = ZPoolStatus(this.pool_name)
        #     output = status.execute()
        #
        #     if (output.returncode == 0):
        #         d = json.loads(output.stdout)
        #
        #         vdevs = d.get("pools", {}).get(this.pool_name, {}).get("vdevs", {}).get(this.pool_name, {}).get("vdevs", {})
        #
        #         if (len(vdevs) == 1):
        #             # check if raidz is enabled
        #             value = list(vdevs.keys())[0]
        #
        #             if (vdevs[value]['vdev_type'] == 'raidz'):
        #                 cmd = ZPoolAttach(this.pool_name, vdevs[value]['name'],new_device)
        #
        #     if (cmd is None):
        #         raise ErrorMessage.get_error(ErrorMessage.E_DISK_ATTACH(new_device))
        #
        # else:
        #     cmd = ZPoolAdd(this.pool_name,new_device)
        #
        # trans = RemoteCommandLineTransaction(socket.AF_UNIX,
        #                                      socket.SOCK_STREAM,
        #                                      SOCK_PATH, cmd)
        #
        # output = trans.run()
        #
        # if (not trans.success):
        #     raise ErrorMessage.get_error(ErrorMessage.E_DISK_ATTACH(output[0]['stderr']))
        #
        # this.cfg["pool"]["disks"].append(new_disk_obj.serialise())
        # this.flush_config()

    def get_pool_status_id(this) -> Optional[str]:
        ...


    def recover(this) -> None:
        ...


    def replace(this, old_dev:str, new_dev:Optional[str]=None) -> None:
        ...


    def deconfigure_pool(this) -> None:
        ...
