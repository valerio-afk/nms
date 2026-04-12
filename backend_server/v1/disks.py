from enum import Enum

from .auth import check_permission
from backend_server.utils.cmdl import LSBLK, ZPoolLabelClear, WipeFS, SMARTCTL
from backend_server.utils.config import CONFIG
from backend_server.utils.responses import ErrorMessage, SuccessMessage, SMART, SMARTPowerOnTime, SMARTAttribute
from backend_server.utils.responses import SMARTSelfTestLog
from backend_server.v1.auth import verify_token_factory, verify_token_header_factory
from fastapi import APIRouter, Depends, HTTPException
from nms_shared import ErrorMessages
from nms_shared.disks import Disk
from nms_shared.msg import SuccessMessages
from nms_shared.enums import UserPermissions, DiskStatus
from typing import List, Optional, Dict, Literal
import json


verify_token = verify_token_factory()

disks = APIRouter(
    prefix='/disks',
    tags=['disks'],
    dependencies=[Depends(verify_token)]
)

class SMARTSelfTest(Enum):
    LONG = "long"
    SHORT = "short"


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


def smartctl(device:str) -> SMART:
    cmd = SMARTCTL(device,sudo=True).execute()
    smartctl_data = json.loads(cmd.stdout) if cmd.returncode == 0 else {}

    smart_support = smartctl_data.get("smart_support",{})
    smart_available = smart_support.get("available",False)
    smart_enabled = smart_support.get("enabled", False)
    poweron_time = smartctl_data.get("power_on_time")

    attributes = []
    logs = []

    attributes_keys = []
    self_test_keys = []

    for k in smartctl_data.keys():
        if ("smart_attributes" in k):
            attributes_keys.append(k)
        elif ("smart_self_test_log" in k):
            self_test_keys.append(k)

    for k in attributes_keys:
        for item in smartctl_data.get(k).get("table",{}):
            attributes.append(
                SMARTAttribute(
                    id=item["id"],
                    name=item["name"].replace("_"," "),
                    value=item["value"],
                    worst=item['worst'],
                    thresh=item['thresh'],
                    when_failed=item['when_failed'],
                )
            )

    for k in self_test_keys:
        for item in smartctl_data.get(k).get("standard",{}).get("table",{}):
            type = item.get("type",{}).get("string")
            status = item.get("status",{}).get("string")
            percentage = item.get("status",{}).get("remaining_percent",None)
            passed = item.get("status", {}).get("passed",False)

            if (type is not None):
                logs.append(
                    SMARTSelfTestLog(
                        type=type,
                        status=status,
                        progress=percentage,
                        passed=passed
                    )
                )


    return SMART(
        device = smartctl_data.get('device',{}).get("name",device),
        available=smart_available,
        enabled=smart_enabled,
        passed=smartctl_data.get("smart_status",{}).get("passed"),
        poweron_time=SMARTPowerOnTime(**poweron_time) if poweron_time is not None else None,
        temperature=smartctl_data.get("temperature",{}).get("current"),
        attributes=attributes,
        self_test_logs=logs,
    )

@disks.get("/get/sys-disks",
          response_model=List[Disk],
          responses={
              500: {"description": "Any internal error to retrieve system disks"},
            },
          summary="Provides all the disks installed in the system",
          )
def sys_disks(token:dict=Depends(verify_token)) -> List[Disk]:
    check_permission(token.get("username"), UserPermissions.CLIENT_DASHBOARD_DISKS)
    return get_system_disks()

@disks.get("/get/disks",
          response_model=List[Disk],
          responses={
              500: {"description": "Any internal error to retrieve system disks"},
            },
          summary="Provides all the disks in the array, attachable, and detached",
          )
def get_all_disks(token:dict=Depends(verify_token)) -> List[Disk]:
    check_permission(token.get("username"), UserPermissions.CLIENT_DASHBOARD_DISKS)
    return get_disks()

@disks.post("/format",
            responses={
              500: {"description": "Any internal error to retrieve system disks"},
            },
          summary="Format a specific disk"
           )
def perform_format_disk(dev:str,auth:Dict=Depends(verify_token_header_factory("format-disk"))) -> Optional[Dict]:
    check_permission(auth.get("username"), UserPermissions.POOL_DISKS_FORMAT)
    format_disk(dev)
    CONFIG.warning(f"`{dev}` has been formatted")

    return {"detail": SuccessMessage(code=SuccessMessages.S_DISK_FORMATTED.name,params=[dev])}

@disks.get("/smart",response_model=SMART,summary="Retrieves SMART information from a given device")
def get_smart_info(dev:str,token:dict=Depends(verify_token)) -> SMART:
    check_permission(token.get("username"), UserPermissions.POOL_DISKS_HEALTH)

    return smartctl(dev)

@disks.post("/smart/test/{test}",summary="Run a SMART self-test")
def smart_self_test(test:SMARTSelfTest,dev:str,token:dict=Depends(verify_token)) -> Dict:
    check_permission(token.get("username"), UserPermissions.POOL_DISKS_HEALTH)

    cmd = SMARTCTL(dev,SMARTCTL.SMARTCTLActions.TEST,test.value,sudo=True).execute()

    if (cmd.returncode == 0):
        return {"detail": SuccessMessage(code=SuccessMessages.S_DISK_SELF_TEST.name,params=[dev])}
    else:
        error = f"{cmd.stderr}\n{cmd.stdout}".strip()
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_DISK_SELF_TEST.name,params=[dev,error]))

