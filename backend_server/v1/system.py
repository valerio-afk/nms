from backend_server.utils.cmdl import Shutdown, Reboot, SystemCtlRestart, LocalCommandLineTransaction, JournalCtl
from backend_server.utils.cmdl import TarArchive, LS, LMSensors
from backend_server.utils.config import CONFIG
from backend_server.utils.inet import DistroFamilies
from backend_server.utils.responses import BackendProperty, BackgroundTask, ErrorMessage, Sensor, SensorType
from backend_server.utils.responses import SensorMetric
from backend_server.utils.scheduler import SCHEDULER
from backend_server.utils.threads import AptGetUpdateThread, AptGetUpgradeThread, NMSUpdate, DNFCheckUpdateThread
from backend_server.utils.threads import DNFUpgradeThread
from backend_server.v1.auth import verify_token_factory, UserPermissions, check_permission
from backend_server.v1.net import net_counter
from backend_server.v1.disks import smartctl, get_system_disks
from collections import OrderedDict
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException
from nms_shared import ErrorMessages
from nms_shared.constants import APT_LISTS
from nms_shared.enums import LogFilter
from requests.exceptions import HTTPError
from typing import Optional, Dict, Union, List
import datetime
import json
import os
import platform
import psutil
import re
import requests


verify_token = verify_token_factory()

system = APIRouter(
    prefix='/system',
    tags=['system'],
    dependencies=[Depends(verify_token)]
)

system_sensors = APIRouter(
    prefix='/system',
    tags=['system']
)


def last_apt_time() -> Optional[int]:
    times = []
    for fname in os.listdir(APT_LISTS):
        path = os.path.join(APT_LISTS, fname)
        if os.path.isfile(path):
            times.append(os.path.getmtime(path))

    if times:
        return max(times)
    return None

def get_cpu_name() -> Optional[str]:
    with open("/proc/cpuinfo") as f:
        for line in f:
            if "model name" in line:
                return line.split(": ")[1].strip()
    return None

def system_information() -> Dict[str, str]:
    from backend_server import __version__

    sys_info = OrderedDict()

    # uptime
    boot_ts = psutil.boot_time()  # epoch seconds when system booted

    sys_info['uptime'] = boot_ts

    # NMS version

    sys_info['nms_ver'] = __version__
    # CPU

    sys_info['cpu'] = f"{get_cpu_name()} with {psutil.cpu_count(logical=True)} core(s)"
    # OS

    sys_info['os'] = " ".join([platform.system(), platform.release(), platform.version(), platform.machine()])

    # cpu load

    sys_info['cpu_load'] = psutil.cpu_percent(interval=1)
    # memory load

    sys_info['memory_load'] = psutil.virtual_memory().percent

    # net_conunters
    sys_info['net_counters'] = net_counter()

    return sys_info

def restart_services(username) -> None:
    cmds = [SystemCtlRestart(service) for service in CONFIG.systemd_services]

    CONFIG.warning(f"systemd services restart requested by {username}. Be right back.")

    if (len(cmds) > 0):
        trans = LocalCommandLineTransaction(*cmds)
        trans.run()

def coretemp_parser(data:dict) -> List[Sensor]:
    sensors = []
    package_re = re.compile(r"Package id ([0-9]+)")
    core_re = re.compile(r"Core ([0-9]+)")
    temp_re = re.compile(r"temp[0-9]+_input")

    for k,v in data.items():
        name = None

        if (m:= package_re.match(k)):
            id = int(m.group(1))
            name = f"CPU {id+1}"
        elif (m:= core_re.match(k)):
            id = int(m.group(1))
            name = f"Core {id+1}"

        if ((name is not None) and (isinstance(v, dict))):
            for tk,tv in v.items():
                if (temp_re.match(tk)):
                    sensors.append(Sensor(
                        device=SensorType.CPU,
                        name=name,
                        value=tv,
                        metric=SensorMetric.CELSIUS))

    return sensors

def anyfan_parser(data:dict) -> List[Sensor]:
    sensors = []
    fan_re = re.compile(r"fan([0-9]+)")

    for k,v in data.items():
        if (m:= fan_re.match(k)):
            id = int(m.group(1))
            fan_key = f"{k}_input"

            sensors.append(Sensor(
                device=SensorType.FAN,
                name=f"Fan {id}",
                value=v[fan_key],
                metric=SensorMetric.RPM
            ))

    return sensors


def hddtemp_parser(data:List[str]) -> List[Sensor]:
    sensors = []

    for l in data:
        dev,_,temp = l.split(":")
        temp_value = float(temp.strip("°C\n "))
        sensors.append(Sensor(
            device=SensorType.HDD,
            name=dev,
            value=temp_value,
            metric=SensorMetric.CELSIUS
        ))

    return sensors




class SystemProperties(Enum):
    system_information = "system_information"
    system_updates = "system_updates"
    last_apt_time = "last_apt_time"

class AptGetActions(Enum):
    update = "update"
    upgrade = "upgrade"



@system.get("/get/{prop}",
          response_model=BackendProperty,
          responses={
              500: {"description": "Any internal error to retrieve pool information"},
              404: {"description": "Invalid system property"},
            },
          summary="Get a configuration/status system property"
          )
def system_get_property(prop:SystemProperties,token:dict=Depends(verify_token)) -> Optional[BackendProperty]:
    check_permission(token.get("username"), UserPermissions.CLIENT_DASHBOARD_ADVANCED)
    match(prop):
        case SystemProperties.system_information:
            return BackendProperty(property=prop.name, value=system_information())
        case SystemProperties.system_updates:
            return BackendProperty(property=prop.name, value=CONFIG.system_updates)
        case SystemProperties.last_apt_time:
            return BackendProperty(property=prop.name, value=CONFIG.last_apt)
        # case _:
        #     CONFIG.error(f"Requested invalid system property {prop}")
        #     raise HTTPException(status_code=404, detail=f"Property {prop} not valid for system")


@system.post('/shutdown',summary="Power off the NAS")
def shutdown(token:dict=Depends(verify_token)):
    check_permission(username:=token.get("username"), UserPermissions.SYS_ADMIN_ACPI)
    CONFIG.warning(f"System shutdown requested by {username}. Goodbye")
    Shutdown().execute()


@system.post('/restart',summary="Reboot the NAS")
def restart(token:dict=Depends(verify_token)):
    check_permission(username:=token.get("username"), UserPermissions.SYS_ADMIN_ACPI)
    CONFIG.warning(f"System reboot requested by {username}. See you later")
    Reboot().execute()

@system.post('/restart-systemd-services',summary="Restart main system services")
def restart_systemd_services(token:dict=Depends(verify_token)) -> None:
    check_permission(username:=token.get("username"), UserPermissions.SYS_ADMIN_SYSTEMCTL)

    restart_services(username)

@system.post('/apt/{action}',
            responses={
              500: {"description": "Any internal error"},
            },
            summary="Perform apt-get update/upgrade commands",
            response_model=BackgroundTask
            )
def apt_get(action:AptGetActions,token:dict=Depends(verify_token)) -> BackgroundTask:
    check_permission(username:=token.get("username"), UserPermissions.SYS_ADMIN_UPDATES)

    match (CONFIG.distro_family):
        case DistroFamilies.DEB:
            update_thread = AptGetUpdateThread
            upgrade_thread = AptGetUpgradeThread
        case DistroFamilies.RH:
            update_thread = DNFCheckUpdateThread
            upgrade_thread = DNFUpgradeThread
        case _:
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_APT_UNK.name))

    match (action):
        case AptGetActions.update:
            task = update_thread()
            task_id = SCHEDULER.schedule(task)
            CONFIG.last_apt = int(datetime.datetime.now().timestamp())
            log_action="update"
        case AptGetActions.upgrade:
            task = upgrade_thread()
            task_id = SCHEDULER.schedule(task)
            log_action = "upgrade"

    CONFIG.info(f"apt {log_action} requested by {username} with task id {task_id}")

    return BackgroundTask(task_id=task_id,running=True,progress=None,eta=None,detail=None)

@system.post("/nms/updates", summary="Retrieve information for new NMS updates from GitHub")
def get_latest_github_release(token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_UPDATES)

    response = requests.get("https://api.github.com/repos/valerio-afk/nms/releases/latest")

    try:
        response.raise_for_status()
    except HTTPError:
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_SYSTEM_UPDATES.name))

    try:
        d = response.json()
    except Exception:
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_UNKNOWN_RESPONSE.name))

    name = d.get("tag_name")
    url = d.get("tarball_url")

    if ((name is not None) and (url is not None)):
        CONFIG.new_nms_update(name,url)
        CONFIG.flush_config()

@system.get("/nms/updates", summary="Provides information related to the newest NMS version retrieved.")
def get_latest_github_release(token:dict=Depends(verify_token)) -> Optional[Dict]:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_UPDATES)
    return CONFIG.nms_updates


@system.patch("/nms/updates", summary="Update NMS",response_model=Optional[BackgroundTask])
def nms_update(token:dict=Depends(verify_token)) -> Optional[BackgroundTask]:
    check_permission(username:=token.get("username"), UserPermissions.SYS_ADMIN_UPDATES)

    thread = NMSUpdate(lambda: restart_services(username))
    task_id = SCHEDULER.schedule(thread)

    CONFIG.info(f"NMS update in progress requested by {username} with task id {task_id}")

    return BackgroundTask(task_id=task_id, running=True, progress=None, eta=None, detail=None)




@system.get("/task/{task_id}",
              responses={500: {"description": "Any internal error while disabling an access services"}},
              summary="Get the information of a background task",
              response_model=Optional[Union[BackgroundTask,Dict]]
)
def get_task_info(task_id: str,token:dict=Depends(verify_token)) ->Optional[Union[BackgroundTask,Dict]]:
    check_permission(token.get("username"), UserPermissions.CLIENT_DASHBOARD_ADVANCED)
    task = SCHEDULER.get_task_by_id(task_id)

    if (task is None):
        return None

    thread = task.thread

    if (thread.has_exception):
        raise thread.message


    return BackgroundTask(task_id=task_id,
                          running=thread.is_running,
                          progress=thread.progress,
                          eta=thread.eta,
                          detail=thread.message
                          )


@system.get("/logs/{filter}",
              responses={500: {"description": "Any internal error while disabling an access services"}},
              response_model=Optional[str],
              summary="Retrieve system logs",
)
def journalctl(filter:LogFilter,
               date_from:Optional[int]=None,
               date_to:Optional[int]=None,
               token:dict=Depends(verify_token)) -> Optional[str]:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_LOGS)
    service = None

    if (date_to is None):
        date_to = int(datetime.datetime.now().timestamp())
    if (date_from is None):
        date_from = date_to - datetime.timedelta(hours=1).total_seconds()

    since = datetime.datetime.fromtimestamp(date_from).strftime("%Y-%m-%d %H:%M:%S")
    until = datetime.datetime.fromtimestamp(date_to).strftime("%Y-%m-%d %H:%M:%S")

    match (filter):
        case LogFilter.FRONTEND:
            service = "nmswebapp.service"
        case LogFilter.BACKEND:
            service = "nmsbackend.service"
        case LogFilter.WEB_SERVER:
            service = "nginx.service"

    cmd = JournalCtl(service,since=since,until=until)

    process = cmd.execute()

    if (process.returncode == 0):
        return process.stdout
    else:
        return process.stderr

@system.get("/test",summary="Test checking if the client/server connection works properly")
def test(token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.CLIENT_DASHBOARD_ACCESS)

@system.post("/make-dist",summary="Create a tarball archive with NMS distribution. The output file will be saved in NMS root directory")
def make_tarball(token:dict=Depends(verify_token)) -> None:
    u = CONFIG.get_user(token.get("username"))
    from backend_server import __version__ as version

    if (not u.admin):
        raise HTTPException(status_code=401)

    pwd = os.getcwd()

    ls = LS(pwd).execute()

    cmd = TarArchive(
        pwd,
        f"nms-{version}.tar.xz",
        action=TarArchive.TarAction.CREATE,
        compression=TarArchive.TarCompression.XZ,
        files=ls.stdout.splitlines(),
        cwd = pwd,
        exclude=[
            ".idea",
            "box/dist",
            "box/node_modules",
            ".gitignore",
            ".github",
            ".gitattributes",
            ".git",
            "__pycache__",
            "build",
            "nms_shared.egg-info",
            "pots",
            "nms.json",
            "*.tar*"
        ]
    ).execute()

    if (cmd.returncode != 0):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_SYSTEM_DIST.name,params=[cmd.stderr]))



@system_sensors.get("/sensors",response_model=List[Sensor],summary="Returns sensor data information (temp, fans, etc.)")
def get_sensors() -> List[Sensor]:
    sensors = []

    lmsensors_cmd = LMSensors().execute()
    lmsensors = json.loads(lmsensors_cmd.stdout) if lmsensors_cmd.returncode == 0 else {}

    for sensor,data in lmsensors.items():
        if ("coretemp" in sensor):
            sensors+=coretemp_parser(data)
        if (len(fans:=anyfan_parser(data))>0):
            sensors+=fans

    for d in get_system_disks():
        smart = smartctl(d.path)

        if (smart.temperature is not None):
            sensors.append(Sensor(
                device=SensorType.HDD,
                name=d.path,
                value=smart.temperature,
                metric=SensorMetric.CELSIUS
            ))

    return sensors

