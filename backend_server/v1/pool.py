from pydantic import BaseModel

from backend_server.utils.cmdl import CommandLine, ZFSLoadKey, ZFSMount, LocalCommandLineTransaction, ZFSUnmount, \
                                      ZFSUnLoadKey, ZFSDestroy, ZFSCreate, ZPoolStatus, ZFSList, ZPoolExport, \
                                      ZPoolImport, CreateKey, ZPoolCreate, ZPoolDestroy, ZPoolClear, ZPoolReplace
from backend_server.utils.config import CONFIG
from backend_server.utils.responses import ExpasionStatus, BackendProperty, ErrorMessage
from backend_server.v1.auth import verify_token_factory
from datetime import timedelta
from enum import Enum
from fastapi import HTTPException, APIRouter, Depends, UploadFile, File
from nms_shared import ErrorMessages
from nms_shared.constants import KEYPATH
from nms_shared.enums import DiskStatus
from nms_shared.disks import Disk
from typing import  Optional, List, Callable
import base64
import json
import os
import re
import subprocess
import traceback


pool = APIRouter(
    prefix='/pool',
    tags=['pool'],
    dependencies=[Depends(verify_token_factory())]
)
remove_partition:Callable[[str],str] = lambda path : re.sub(r"-part[0-9]$","",path)

def unmount():
    if (not CONFIG.is_pool_configured):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_NO_CONF.name))

    if (not CONFIG.is_mounted):
        return

    #TODO: disable all access services

    cmds: List[CommandLine] = [
        ZFSUnmount(CONFIG.pool_name, CONFIG.dataset_name),
        ZFSUnmount(CONFIG.pool_name)
    ]

    if (CONFIG.has_encryption):
        cmds.append(ZFSUnLoadKey(CONFIG.pool_name))


    trans = LocalCommandLineTransaction(*cmds)

    output = trans.run()

    if (not trans.success):
        errors = "\n".join([o['stderr'] for o in output])
        raise ErrorMessage(code=ErrorMessages.E_POOL_UNMOUNT.name,params=[errors])

def get_array_expansion_status() -> ExpasionStatus:
    if (not CONFIG.is_pool_configured()):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_NO_CONF.name))

    if (not CONFIG.has_redundancy):
        return ExpasionStatus(is_running=False, eta=None, progress=None)

    cmd = ZPoolStatus(CONFIG.pool_name,show_json=False)

    output = cmd.execute()

    if (output.returncode != 0):
        error = output[0]['stderr']
        raise ErrorMessage(code=ErrorMessages.E_POOL_EXPAND_STATUS.name,params=[error])

    zpool_output = output.stdout


    # Case 1: percentage + ETA available
    with_eta = re.search(
        r'([\d.]+)%\s+done,\s+([\d:]+)\s+to\s+go',
        zpool_output,
        re.IGNORECASE
    )

    if with_eta:
        pct = float(with_eta.group(1))
        h, m, s = map(int, with_eta.group(2).split(":"))
        return ExpasionStatus(progress=pct, eta=timedelta(hours=h, minutes=m, seconds=s), is_running=True)

    # Case 2: percentage but ETA explicitly unavailable
    no_eta = re.search(
        r'([\d.]+)%\s+done,.*no\s+estimated\s+time',
        zpool_output,
        re.IGNORECASE
    )

    if no_eta:
        pct = float(no_eta.group(1))
        return ExpasionStatus(progress=pct, eta=None, is_running=True)

    # case 3: done
    completed = re.search(r'expand:\s+expanded', zpool_output,
        re.IGNORECASE)
    if completed:
        return ExpasionStatus(progress=100, eta=None, is_running=False)

    return ExpasionStatus(progress=None, eta=None, is_running=True)

def get_pool_disks() -> List[Disk]:
    from .disks import get_system_disks

    if (not CONFIG.is_pool_configured):
        return []

    trans = LocalCommandLineTransaction(ZPoolStatus(CONFIG.pool_name))
    output = trans.run()

    if ((trans.success) and (len(output) == 1)):
        stdout = output[0].get('stdout',None)

        try:
            d = json.loads(stdout)
            pool_name = CONFIG.pool_name

            if (CONFIG.has_redundancy):
                disks = d.get("pools",{}) \
                        .get(pool_name,{}) \
                        .get("vdevs",{}) \
                        .get(pool_name,{}) \
                        .get("vdevs",{}) \
                        .popitem()[1] \
                        .get("vdevs",{})
            else:
                disks = d.get("pools", {}) \
                    .get(pool_name, {}) \
                    .get("vdevs", {}) \
                    .get(pool_name, {}) \
                    .get("vdevs", {})


            paths = [remove_partition(d['path']) for d in disks.values()]

            attached_disks = [ x for x in get_system_disks() if x.has_any_paths(paths) ]
            detached_disks = []

            for d in attached_disks:
                for x in disks.values():
                    path = x.get('path',None)
                    if path is not None:
                        path = remove_partition(path)
                        if d.has_path(path):
                            match (x.get("state")):
                                case 'ONLINE':
                                    d.status = DiskStatus.ONLINE
                                case 'OFFLINE':
                                    d.status = DiskStatus.OFFLINE
                                case _:
                                    d.status = DiskStatus.CORRUPTED

            for d in disks.values():
                if (d.get("not_present",0)==1) or (d.get("state",None) == "REMOVED"):
                    old_path = d.get("path") or d.get("was","")

                    old_path = remove_partition(old_path)

                    offline_disk = Disk(
                        name=d.get("name"),
                        model="Removed disk",
                        serial="N/A",
                        size=int(d.get("phys_space","0")),
                        path=d.get("was",""),
                        status=DiskStatus.OFFLINE
                    )

                    for cfg_disk in CONFIG.configured_disks:
                        if cfg_disk.has_path(old_path):
                            offline_disk.name = cfg_disk.name
                            offline_disk.model = cfg_disk.model
                            offline_disk.serial = cfg_disk.serial
                            offline_disk.size = cfg_disk.size
                            offline_disk.cached_physical_paths = cfg_disk.cached_physical_paths

                    detached_disks.append(offline_disk)


            return attached_disks + detached_disks

        except Exception as e:
            tb = traceback.format_exc()
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_DISKS.name,params=[f"{str(e)}\n{tb}"]))

    return []

def get_attachable_disks() -> List[Disk]:
    from .disks import get_system_disks
    disks = [d for d in get_system_disks() if d.status == DiskStatus.NEW]
    config_disk = get_pool_disks()

    physical_paths = []

    for d in config_disk:
        physical_paths.extend(d.physical_paths)

    physical_paths = set(physical_paths)
    attachable_disks = []

    for d in disks:

        if (len(physical_paths.intersection(set(d.physical_paths))) == 0):
            attachable_disks.append(d)

    return attachable_disks



def is_a_pool_present() -> bool:
    zfs_list = ZFSList()
    zfs_list_output = zfs_list.execute()

    if (zfs_list_output.returncode == 0):
        output = zfs_list_output.stdout
        d = json.loads(output)

        return len(d.get("datasets",{})) > 0

    return False


def get_importable_pools() -> List[dict]:

    cmd = ZPoolImport()

    process = cmd.execute()

    if (process.returncode != 0):
        raise Exception("Unable to get importable pools")

    result = process.stdout

    pools = []
    current_pool = None
    in_config = False
    read_status_action = False

    for line in result.splitlines():
        line = line.rstrip()

        # pool name
        m = re.match(r"\s*pool:\s+(\S+)", line)
        if m:
            current_pool = {
                "name": m.group(1),
                "disks": [],
                "message": "",
                "state": None
            }
            pools.append(current_pool)
            in_config = False
            continue

        line = line.strip()

        # start of config section
        if line == "config:":
            in_config = True
            read_status_action = False
            continue

        if (line.startswith("status:") or line.startswith("action:")) and current_pool:
            read_status_action = True
            _,message = line.split(":",1)
            current_pool["message"] += " "+message.strip()
            continue
        elif read_status_action:
            current_pool["message"] += " " + line
            continue

        if (line.startswith("state:") and current_pool):
            _,state = line.split(":",1)
            current_pool["state"] = state.strip()
            continue

        if not in_config or current_pool is None:
            continue


        # disk lines are indented and have ONLINE/DEGRADED/etc
        m = re.match(r"(\S+)\s+(ONLINE|DEGRADED|FAULTED|OFFLINE|UNAVAIL)", line)
        if m:
            dev = m.group(1)

            # skip vdevs like mirror-0, raidz1-0, etc
            if (not re.match(r"(mirror|raidz)\S*", dev)) and (current_pool["name"] not in line):
                output = subprocess.run(['find','/dev','-name',f"*{dev}"],capture_output=True)

                if output.returncode == 0:
                    lines = output.stdout.decode('utf8').splitlines()
                    if (len(lines)>0):
                        dev = lines[0].strip()

                        parts = dev.split(os.path.sep)
                        if (len(parts)>2):
                            dev = os.path.realpath(dev)

                current_pool["disks"].append(dev)

    for d in pools:
        d['message'] = d['message'].strip()

    return pools

def get_tank_key() -> Optional[str]:
    if (not CONFIG.has_encryption):
        return None

    fname = CONFIG.key_filename

    if (os.path.isabs(fname) and (fname.startswith("/root"))):
        path = fname
    else:
        path = os.path.join("/", "root", fname)

    result = subprocess.run(
        ["sudo", "cat", path],
        stdout=subprocess.PIPE,
        check=True
    )

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_KEY.name,params=[result.stderr.decode('utf8')]))

    return base64.b64encode(result.stdout).decode("ascii")

def get_pool_status_id() -> Optional[str]:
    if (CONFIG.is_pool_configured):
        pool = CONFIG.pool_name
        trans = LocalCommandLineTransaction(ZPoolStatus(pool))
        output = trans.run()
        if (trans.success) and (len(output) > 0):
            output = output[0].get("stdout",{})
            d = json.loads(output)

            root = d.get("pools", {}).get(pool,{})
            return root.get("msgid",None)

def recover() -> None:
    trans = LocalCommandLineTransaction(ZPoolClear(CONFIG.pool_name,True))

    output = trans.run()

    if (not trans.success):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_RECOVERY.name, params=[output[0]['stderr']]))


class PoolProperties(Enum):
    pool_name = "pool_name"
    dataset_name = "dataset_name"
    mountpoint = "mountpoint"
    is_mounted = "is_mounted"
    is_configured = "is_configured"
    is_present = "is_present"
    any_pool_present = "any_pool_present"
    pool_capacity = "pool_capacity"
    expansion_status = "expansion_status"
    pool_list = "pool_list"
    encryption_key = "encryption_key"
    status_id = "status_id"


@pool.get("/get/disks",
          response_model=List[Disk],
          responses={500: {"description": "Any internal error to retrieve pool information"}},
          summary="Get the list of disks in the array"
          )
def pool_disks() -> List[Disk]:
    return get_pool_disks()

@pool.get("/get/attachable-disks",
          response_model=List[Disk],
          responses={500: {"description": "Any internal error to retrieve pool information"}},
          summary="Get the list of new disks that can be attached/added to the array"
          )
def attachable_disks() -> List[Disk]:
    return get_attachable_disks()




@pool.get("/get/{prop}",
          response_model=BackendProperty,
          responses={
              500: {"description": "Any internal error to retrieve pool information"},
              404: {"description": "Invalid pool property"},
            },
          summary="Get a configuration/status pool property"
          )
def pool_get_property(prop:PoolProperties) -> Optional[BackendProperty]:
    try:
        match prop:
            case PoolProperties.pool_name:
                return BackendProperty(property=prop.value, value=CONFIG.pool_name)
            case PoolProperties.dataset_name:
                return BackendProperty(property=prop.value, value=CONFIG.dataset_name)
            case PoolProperties.mountpoint:
                return BackendProperty(property=prop.value, value=CONFIG.mountpoint)
            case PoolProperties.is_mounted:
                return BackendProperty(property=prop.value, value=CONFIG.is_mounted)
            case PoolProperties.is_configured:
                return BackendProperty(property=prop.value, value=CONFIG.is_pool_configured)
            case PoolProperties.is_present:
                return BackendProperty(property=prop.value, value=CONFIG.is_pool_present)
            case PoolProperties.any_pool_present:
                return BackendProperty(property=prop.value, value=is_a_pool_present())
            case PoolProperties.pool_capacity:
                return BackendProperty(property=prop.value, value=CONFIG.get_pool_capacity)
            case PoolProperties.expansion_status:
                return BackendProperty(property=prop.value, value=get_array_expansion_status())
            case PoolProperties.pool_list:
                return BackendProperty(property=prop.value, value=get_importable_pools())
            case PoolProperties.encryption_key:
                return BackendProperty(property=prop.value, value=get_tank_key())
            case PoolProperties.status_id:
                return BackendProperty(property=prop.value, value=get_pool_status_id())
            case _:
                CONFIG.error(f"Requested invalid pool property {prop}")
                raise HTTPException(status_code=404, detail=f"Property {prop} not valid for pool")
    except HTTPException as e:
        raise e
    except Exception as err:
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_PROPERTY.name,params=[prop.name,str(err)]))

@pool.post(
    "/mount",
    responses={500: {"description": "Missing configuration/Other internal errors"}},
    summary="Mount the disk array"
)
def pool_mount() -> None:
    if (not CONFIG.is_pool_configured):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_NO_CONF.name))

    if (CONFIG.is_mounted):
        return

    cmds = []

    if (CONFIG.has_encryption):
        cmds.append(ZFSLoadKey(CONFIG.pool_name, CONFIG.key_filename))

    cmds.append(ZFSMount(CONFIG.pool_name))
    cmds.append(ZFSMount(CONFIG.pool_name, CONFIG.dataset_name))

    trans = LocalCommandLineTransaction(*cmds)

    output = trans.run()

    if (not trans.success):
        errors = "\n".join([o['stderr'] for o in output])
        raise ErrorMessage(code=ErrorMessages.E_POOL_MOUNT.name,params=[errors])

@pool.post(
    "/unmount",
    responses={500: {"description": "Missing configuration/Other internal errors"}},
    summary="Unmount the disk array"
)
def pool_unmount() -> None:
        unmount()

@pool.post(
    "/format",
    responses={500: {"description": "Any internal errors"}},
    summary="Destroy and recreate a new disk array"
)
def pool_format() -> None:
    if (not CONFIG.is_pool_configured):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_NO_CONF.name))

    # TODO: disable all access services

    unmount()

    pool = CONFIG.pool_name
    dataset = CONFIG.dataset_name

    commands = [
        ZFSDestroy(pool, dataset),
        ZFSCreate(pool, dataset)
    ]

    trans = LocalCommandLineTransaction(*commands)

    output = trans.run()

    if (not trans.success):
        errors = "\n ".join([x["stderr"] for x in output])
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_FORMAT.name,params=[errors]))



@pool.post(
    "/detach",
    responses={500: {"description": "Any internal errors"}},
    summary="Detach the disk array (it will not be visible anymore) without deleting it"
)
def pool_detach() -> None:
    if (not CONFIG.is_pool_configured):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_NO_CONF.name))

    cmd = ZPoolExport(CONFIG.pool_name)

    process = cmd.execute()

    if (process.returncode != 0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_DETACH.name,params=[process.stderr.decode()]))

    CONFIG.deinit_pool()
    CONFIG.flush_config()

@pool.post(
    "/attach/{pool_name}",
    responses={500: {"description": "Any internal errors"}},
    summary="Attach an existing disk array"
)
def pool_attach(pool_name:str,load_key:bool=False) -> None:
    if (CONFIG.is_pool_configured):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_CONFIG.name))

    commands: List[CommandLine] = [ZPoolImport(pool_name)]

    if (load_key):
        commands.append(ZFSLoadKey(pool_name, KEYPATH))


    trans = LocalCommandLineTransaction(*commands)
    output = trans.run()

    if (not trans.success):
        errors = "\n".join([o['stderr'] for o in output])
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_ATTACH.name, params=[errors]))



    CONFIG.init_pool()


    try:
        if (not CONFIG.is_mounted):
            pool_mount()

        CONFIG.flush_config()
    except Exception as e:
        #revert configuration to previous state
        CONFIG.load_configuration_file()
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_ATTACH.name, params=[str(e)]))


class CreatePool(BaseModel):
    pool_name: str
    dataset_name: str
    redundancy: bool
    encryption: Optional[str]
    compression: bool
    disks: List[str]

@pool.post("/create",
    responses={500: {"description": "Any internal errors"}},
    summary="Create a new disk array",)
def create_disk_array(data:CreatePool) -> None:
    from .disks import get_disks, format_disk
    from .fs import change_permissions
    if (CONFIG.is_pool_configured):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_CONFIG.name))

    disks_objs = [d for d in get_disks() if (d.status == DiskStatus.NEW) and (d.has_any_paths(data.disks))]

    if (len(disks_objs) < len(data.disks)):
        for dev in data.disks:
            for d in disks_objs:
                if (not d.has_path(dev)):
                    raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_DISK_UNAVAL.name,params=[dev]))

    if data.redundancy and (len(data.disks) < 3):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_REDUNDANCY_MIN.name))



    for disk in data.disks:
        format_disk(disk)

    commands = []
    enc_key = None

    if data.encryption is not None:
        enc_key = KEYPATH
        keygen = CreateKey(enc_key)
        commands.append(keygen)

    commands.append(ZPoolCreate(data.disks, data.redundancy, enc_key, data.compression, data.pool_name))
    commands.append(ZFSCreate(data.pool_name, data.dataset_name))

    trans = LocalCommandLineTransaction(*commands)

    output = trans.run()

    if (not trans.success):
        if (len(output) == 0):
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_NEW.name))
        else:
            errors = "\n".join([o['stderr'] for o in output])
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_NEW.name,params=[errors]))

    CONFIG.config_pool(
        data.pool_name,
        data.dataset_name,
        data.redundancy,
        enc_key,
        data.compression,
        disks_objs
    )

    CONFIG.flush_config()

    change_permissions(CONFIG.mountpoint)

@pool.post("/destroy",
    responses={500: {"description": "Any internal errors"}},
    summary="Destroy the new disk array",)
def create_disk_array() -> None:
    from .fs import rm_mountpoint
    if (not CONFIG.is_pool_configured):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_NO_CONF.name))

    #TODO: disable all services

    mountpoint = CONFIG.mountpoint

    try:
        unmount()
    except:
        ...

    pool = CONFIG.pool_name
    dataset = CONFIG.dataset_name

    commands = [
        ZFSDestroy(pool, dataset),
        ZPoolDestroy(pool)
    ]

    trans = LocalCommandLineTransaction(*commands)

    output = trans.run()

    if (not trans.success):
        errors = "\n ".join([x["stderr"] for x in output])
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_DESTROY.name, params=[errors]))

    CONFIG.deinit_pool()
    CONFIG.flush_config()

    try:
        rm_mountpoint(mountpoint)
    except:
        ... # it means that zpool already removed it

@pool.post("/import-key",
    responses={500: {"description": "Any internal errors"}},
    summary="Import encryption key for a disk array",)
async def import_key(key_file: UploadFile = File(...)) -> None:
    key = await key_file.read()

    path = KEYPATH

    proc = subprocess.run(
        ["sudo", "tee", path],
        input=key,
        stdout=subprocess.DEVNULL,  # avoid echoing back
        stderr=subprocess.PIPE,
        check=True,
    )

    if (proc.returncode != 0):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_KEY_IMPORT.name, params=[proc.stdout.decode()]))

    CONFIG.key_filename = path
    CONFIG.flush_config()

@pool.post("/recover",
    responses={500: {"description": "Any internal errors"}},
    summary="Attempts to recover from errors in the disk array",)
def attempt_recovery() -> None:
    recover()

@pool.post("/recover",
    responses={500: {"description": "Any internal errors"}},
    summary="Replace a device with another device in the disk array",)
def replace(old_dev:str, new_dev:str) -> None:
    cmd =  ZPoolReplace(CONFIG.pool_name, old_dev, new_dev)

    process = cmd.execute()

    if (process.returncode != 0):
        error = process.stderr.decode()
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_DISK_REPLACE.name, params=[old_dev, new_dev, error]))


#TODO: EXPAND