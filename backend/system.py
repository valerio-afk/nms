from backend.daemons import DaemonsMixin
from cmdl import RemoteCommandLineTransaction, Reboot, Shutdown, SystemCtlRestart,APTGetUpdate, APTGetUpgrade
from collections import OrderedDict
from constants import SOCK_PATH, APT_LISTS
from typing import Optional, List, Dict
import datetime
import os
import platform
import psutil
import socket

def get_cpu_name():
    with open("/proc/cpuinfo") as f:
        for line in f:
            if "model name" in line:
                return line.split(": ")[1].strip()
    return "Unknown CPU"

class SystemMixin (DaemonsMixin):
    @property
    def system_information(this) -> Dict[str, str]:
        from . import __version__

        sys_info = OrderedDict()

        # uptime
        boot_ts = psutil.boot_time()  # epoch seconds when system booted
        boot_dt = datetime.datetime.fromtimestamp(boot_ts)

        sys_info['Uptime'] = f"Since {boot_dt.strftime("%A, %d %B %Y at %H:%M")}"

        # NMS version

        sys_info['NMS Version'] = __version__
        # CPU

        sys_info['CPU'] = f"{get_cpu_name()} with {psutil.cpu_count(logical=True)} core(s)"
        # OS

        sys_info['OS'] = " ".join([platform.system(), platform.release(), platform.version(), platform.machine()])

        # cpu load

        sys_info['_cpu_load'] = psutil.cpu_percent(interval=1)
        # memory load

        sys_info['_memory_load'] = psutil.virtual_memory().percent

        # net_conunters
        sys_info['_net_counters'] = this.get_net_counters

        return sys_info

    @property
    def get_updates(this) -> List[str]:
        return [pkg for pkg in this._cfg.get("updates",{}).get("apt",[])]

    def reboot(this) -> None:

        this.logger.info("Rebooting...")

        try:
            trans = RemoteCommandLineTransaction(socket.AF_UNIX,
                                                 socket.SOCK_STREAM,
                                                 SOCK_PATH, Reboot())

            trans.run()
        except Exception as e:
            this.logger.error(f"Unable to reboot the system: {e}")

    def shutdown(this) -> None:
        this.logger.info("Shutting down...")

        try:
            trans = RemoteCommandLineTransaction(socket.AF_UNIX,
                                                 socket.SOCK_STREAM,
                                                 SOCK_PATH, Shutdown())

            trans.run()
        except Exception as e:
            this.logger.error(f"Unable to shut down the system: {e}")

    def restart_systemd_services(this) -> None:
        cmds = [ SystemCtlRestart(service) for service in this._cfg['systemd'].get('services',[]) ]

        if (len(cmds)>0):
            trans = RemoteCommandLineTransaction(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
                SOCK_PATH,
                *cmds
            )

            trans.run()



    def get_apt_updates(this) -> None:
        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            APTGetUpdate()
        )

        output = trans.run()


        try:
            if (trans.success):
                trans = RemoteCommandLineTransaction(
                    socket.AF_UNIX,
                    socket.SOCK_STREAM,
                    SOCK_PATH,
                    APTGetUpgrade(dry_run=True)
                )

                output = trans.run()

                if (trans.success):
                    stdout = output[0].get("stdout","")

                    updates = []

                    for line in stdout.splitlines():
                        if (line.startswith("Inst ")):
                            pkg = line.split()

                            if (len(pkg)>=2):
                                updates.append(pkg[1])

                    this._cfg['updates']['apt'] = updates
                    this.flush_config()

                else:
                    raise Exception(output[0]['stdout'])
            else:
                raise Exception(output[0]['stdout'])
        except Exception as e:
            raise Exception(f"Could not get list of updates: {str(e)}")

    def get_apt_upgrade(this) -> None:
        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            APTGetUpdate()
        )

        output = trans.run()


        try:
            if (trans.success):
                trans = RemoteCommandLineTransaction(
                    socket.AF_UNIX,
                    socket.SOCK_STREAM,
                    SOCK_PATH,
                    APTGetUpgrade(dry_run=False)
                )

                output = trans.run()

                if (trans.success):
                    this._cfg['updates']['apt'] = []
                    this.flush_config()

                else:
                    raise Exception(output[0]['stdout'])
            else:
                raise Exception(output[0]['stdout'])
        except Exception as e:
            raise Exception(f"Could not install system updates: {str(e)}")

    def last_apt_time(this) -> Optional[datetime.datetime]:
        times = []
        for fname in os.listdir(APT_LISTS):
            path = os.path.join(APT_LISTS, fname)
            if os.path.isfile(path):
                times.append(os.path.getmtime(path))

        if times:
            return datetime.datetime.fromtimestamp(max(times))
        return None
