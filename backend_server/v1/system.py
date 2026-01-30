
from backend_server.v1.net import net_counter
from backend_server.v1.auth import verify_token_factory
from backend_server.utils.config import CONFIG
from backend_server.utils.responses import BackendProperty, ErrorMessage
from backend_server.utils.cmdl import Shutdown, Reboot, SystemCtlRestart, LocalCommandLineTransaction, APTGetUpdate, \
    APTGetUpgrade
from collections import OrderedDict
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException
from nms_shared.constants import APT_LISTS
from typing import Optional, Dict
import datetime
import os
import platform
import psutil

from nms_shared.threads import NMSThread

system = APIRouter(
    prefix='/system',
    tags=['system'],
    dependencies=[Depends(verify_token_factory())]
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
    boot_dt = datetime.datetime.fromtimestamp(boot_ts)

    sys_info['uptime'] = boot_dt.strftime("%A, %d %B %Y at %H:%M")

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


class APTGETThread (NMSThread):
    def run(this) -> None:
        cmd = APTGetUpdate()
        process = cmd.execute()

        try:
            if (process.returncode != 0):
                raise Exception(process.stderr)

            cmd = APTGetUpgrade(dry_run=True)
            process = cmd.execute()

            if (process.returncode != 0):
                raise Exception(process.stderr)

            updates = []

            for line in process.stdout.splitlines():
                if (line.startswith("Inst ")):
                    pkg = line.split()

                    if (len(pkg) >= 2):
                        updates.append(pkg[1])

            CONFIG.system_updates = updates
            CONFIG.flush_config()

        except Exception as e:
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessage.E_APT_GET.name, params=[str(e)]))



@system.get("/get/{prop}",
          response_model=BackendProperty,
          responses={
              500: {"description": "Any internal error to retrieve pool information"},
              404: {"description": "Invalid system property"},
            },
          summary="Get a configuration/status system property"
          )
def system_get_property(prop:SystemProperties) -> Optional[BackendProperty]:
    match(prop):
        case SystemProperties.system_information:
            return BackendProperty(property=prop.name, value=system_information())
        case SystemProperties.system_updates:
            return BackendProperty(property=prop.name, value=CONFIG.system_updates)
        case SystemProperties.last_apt_time:
            return BackendProperty(property=prop.name, value=last_apt_time())
        case _:
            CONFIG.error(f"Requested invalid system property {prop}")
            raise HTTPException(status_code=404, detail=f"Property {prop} not valid for system")


@system.post('/shutdown',summary="Power off the NAS")
def shutdown():
    Shutdown().execute()


@system.post('/restart',summary="Reboot the NAS")
def restart():
    Reboot().execute()

@system.post('/restart-systemd-services',summary="Restart main system services")
def restart_systemd_services() -> None:
    cmds = [SystemCtlRestart(service) for service in CONFIG.systemd_services]

    if (len(cmds) > 0):
        trans = LocalCommandLineTransaction(*cmds)
        trans.run()

@system.get('/apt-updates',
            responses={
              500: {"description": "Any internal error to retrieve updates information"},
            },
            summary="Retrieves packages to be updated from APT")
def apt_updates() -> None:


@system.post('/apt-upgrade',
             responses={
                 500: {"description": "Any internal error to install upgrades"},
             },
             summary="Retrieves packages to be updated from APT")
def apt_upgrade() -> None:
    cmd = APTGetUpdate()
    process = cmd.execute()

    try:
        if (process.returncode != 0):
            raise Exception(process.stderr)

        cmd = APTGetUpgrade(dry_run=False)
        process = cmd.execute()

        if (process.returncode != 0):
            raise Exception(process.stderr)

        CONFIG.system_updates = []
        CONFIG.flush_config()

    except Exception as e:
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessage.E_APT_GET.name, params=[str(e)]))