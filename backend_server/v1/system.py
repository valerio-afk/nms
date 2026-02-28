from backend_server.utils.cmdl import Shutdown, Reboot, SystemCtlRestart, LocalCommandLineTransaction, JournalCtl
from backend_server.utils.config import CONFIG
from backend_server.utils.responses import BackendProperty, BackgroundTask
from backend_server.utils.scheduler import SCHEDULER
from backend_server.utils.threads import AptGetUpdateThread, AptGetUpgradeThread
from backend_server.v1.auth import verify_token_factory, UserPermissions, check_permission
from backend_server.v1.net import net_counter
from collections import OrderedDict
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException
from nms_shared.constants import APT_LISTS
from nms_shared.enums import LogFilter
from typing import Optional, Dict, Union
import datetime
import os
import platform
import psutil

verify_token = verify_token_factory()

system = APIRouter(
    prefix='/system',
    tags=['system'],
    dependencies=[Depends(verify_token)]
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
        case _:
            CONFIG.error(f"Requested invalid system property {prop}")
            raise HTTPException(status_code=404, detail=f"Property {prop} not valid for system")


@system.post('/shutdown',summary="Power off the NAS")
def shutdown(token:dict=Depends(verify_token)):
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_ACPI)
    Shutdown().execute()


@system.post('/restart',summary="Reboot the NAS")
def restart(token:dict=Depends(verify_token)):
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_ACPI)
    Reboot().execute()

@system.post('/restart-systemd-services',summary="Restart main system services")
def restart_systemd_services(token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_SYSTEMCTL)
    cmds = [SystemCtlRestart(service) for service in CONFIG.systemd_services]

    if (len(cmds) > 0):
        trans = LocalCommandLineTransaction(*cmds)
        trans.run()

@system.post('/apt/{action}',
            responses={
              500: {"description": "Any internal error"},
            },
            summary="Perform apt-get update/upgrade commands",
            response_model=BackgroundTask
            )
def apt_get(action:AptGetActions,token:dict=Depends(verify_token)) -> BackgroundTask:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_UPDATES)
    match (action):
        case AptGetActions.update:
            task = AptGetUpdateThread()
            task_id = SCHEDULER.schedule(task)
            CONFIG.last_apt = int(datetime.datetime.now().timestamp())
        case AptGetActions.upgrade:
            task = AptGetUpgradeThread()
            task_id = SCHEDULER.schedule(task)

    return BackgroundTask(task_id=task_id,running=True,progress=None,eta=None,detail=None)



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

    cmd = JournalCtl(service,since=since,until=until)

    process = cmd.execute()

    if (process.returncode == 0):
        return process.stdout
    else:
        return process.stderr

@system.get("/test",summary="Test checking if the client/server connection works properly")
def test(token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.CLIENT_DASHBOARD_ACCESS)