from fastapi import APIRouter, Depends, HTTPException
from backend_server.v1.auth import verify_token_factory
from backend_server.utils.responses import Disk, ErrorMessage
from backend_server.utils.cmdl import LSBLK, ZPoolLabelClear, WipeFS
from typing import List

import json

from nms_shared import ErrorMessages
from nms_shared.enums import DiskStatus

disks = APIRouter(
    prefix='/disks',
    tags=['disks'],
    # dependencies=[Depends(verify_token_factory())]
)


def get_system_disks() -> List[Disk]:
    lsblk = LSBLK()
    lsblk_output = lsblk.execute()
    lsblk_disks = json.loads(lsblk_output.stdout)

    sata_disks = [x for x in lsblk_disks['blockdevices'] if x['tran'] in ['sata', 'spi']]

    return [
        Disk(name=d['name'],
             model=d['model'],
             serial=d['serial'],
             size=d['size'],
             path=d['path'],
             status=DiskStatus.NEW,
             )
        for d in sata_disks
    ]

def get_disks() -> List[Disk]:
    from .pool import get_pool_disks

    pool_disks = get_pool_disks()
    system_disks = get_system_disks()

    detected_disks = []



    for sys_disk in system_disks:
        for pool_disk in pool_disks:
            if (sys_disk==pool_disk):
                detected_disks.append(pool_disk)




    for d in detected_disks:
        pool_disks.remove(d)
        system_disks.remove(d)

    detected_disks.extend(system_disks)
    detected_disks.extend(pool_disks)

    detected_disks.sort(key=lambda x : x.physical_paths)

    return detected_disks

def format_disk(dev:str) -> None:
    cmd1 = ZPoolLabelClear(dev)
    proc1 = cmd1.execute()

    if (proc1.returncode == 0):
        return

    cmd2 = WipeFS(dev)
    proc2 = cmd2.execute()

    if (proc2.returncode != 0):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_DISK_FORMAT.name,params=[dev,proc2.stderr]))

@disks.get("/get/sys-disks",
          response_model=List[Disk],
          responses={
              500: {"description": "Any internal error to retrieve system disks"},
            },
          summary="Provides all the disks installed in the system",
          )
def sys_disks() -> List[Disk]:
    return get_system_disks()

@disks.get("/get/disks",
          response_model=List[Disk],
          responses={
              500: {"description": "Any internal error to retrieve system disks"},
            },
          summary="Provides all the disks in the array, attachable, and detached",
          )
def get_all_disks() -> List[Disk]:
    return get_disks()