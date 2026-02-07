from nms_shared.disks import Disk
from nms_shared.threads import NMSThread
from backend_server.utils.cmdl import ZPoolStatus, APTGetUpdate, APTGetUpgrade
from nms_shared import ErrorMessages, SuccessMessages
from backend_server.utils.responses import ErrorMessage, SuccessMessage
from fastapi import HTTPException
from typing import Optional
import psutil
import time
import json

class NetIOCounter (NMSThread):

    def __init__(this):
        super().__init__()
        this._current_counter = None
        this._bytes_received:int = None
        this._bytes_sent:int = None


    @property
    def bytes_received(this) -> Optional[int]:
        return this._bytes_received if this.is_running else None

    @property
    def bytes_sent(this) -> Optional[int]:
        return this._bytes_sent if this.is_running else None


    def run(this) -> None:
        while (this.is_running):
            counters = psutil.net_io_counters()

            if (this._current_counter is not None):
                this._bytes_received = counters.bytes_recv - this._current_counter.bytes_recv
                this._bytes_sent = counters.bytes_sent - this._current_counter.bytes_sent

            this._current_counter = counters

            time.sleep(1)

class ScrubStateChecker(NMSThread):
    def __init__(this, pool_name: str):
        super().__init__()
        this.pool_name = pool_name

    def run(this) -> None:
        from backend_server.utils.config import CONFIG
        try:
            while (this.is_running):
                output = ZPoolStatus(this.pool_name).execute()

                if (output.returncode == 0):
                    d = json.loads(output.stdout)
                    scan_stats = d.get('pools', {}).get(this.pool_name, {}).get('scan_stats', {})

                    if (scan_stats.get('function', "") == "SCRUB"):
                        if (scan_stats.get('state', "FINISHED") != "FINISHED"):
                            time.sleep(2)
                        else:
                            break
                    else:
                        break
                else:
                    error = output.stderr.decode('utf8')
                    CONFIG.error(f"Scrub state checker: {error}")
                    raise HTTPException(500,detail=ErrorMessage(code=ErrorMessages.E_POOL_SCRUB.name, params=[error]))
        except Exception as e:
            raise e
        finally:
            CONFIG.scrub_stopped()
            CONFIG.flush_config()


        this._message = SuccessMessage(code=SuccessMessages.S_POOL_SCRUB.name)
        CONFIG.info("Scrub state checker terminated successfully")

class PoolExpansionStatus(NMSThread):
    def __init__(this, dev:str):
        super().__init__()
        this._device = dev


    def run(this) -> None:
        from backend_server.utils.config import CONFIG
        from backend_server.v1.pool import get_array_expansion_status
        done = False
        time.sleep(0.5)

        while not done:
            status = get_array_expansion_status()

            if (status.progress is None) and (status.eta is None):
                raise Exception(ErrorMessage.get_error(ErrorMessage.E_POOL_EXPAND_INFO, this._device))
            else:
                if (status.eta is not None):
                    this._eta = status.eta
                    this._progress = status.progress

            done = not status.is_running

            time.sleep(1)

        this._message =  SuccessMessage(code=SuccessMessages.S_POOL_EXPANDED.name)
        CONFIG.info("Pool expansion completed successfully")

class AptGetUpdateThread(NMSThread):
    def run(this) -> None:
        from backend_server.utils.config import CONFIG
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
            raise HTTPException(status_code=500,
                                detail=ErrorMessage(code=ErrorMessage.E_APT_GET.name, params=[str(e)]))

class AptGetUpgradeThread(NMSThread):

    def run(this) -> None:
        from backend_server.utils.config import CONFIG
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
            raise HTTPException(status_code=500,
                                detail=ErrorMessage(code=ErrorMessage.E_APT_GET.name, params=[str(e)]))


class ResilverStateChecker(NMSThread):
    def __init__(this, old_disk:Optional[Disk]=None,new_disk:Optional[Disk]=None):
        super().__init__()
        this.success_message = None
        this._old_disk = old_disk
        this._new_disk = new_disk


    def run(this) -> None:
        from backend_server.utils.config import CONFIG
        pool_name = CONFIG.pool_name
        try:
            while (this.is_running):
                output = ZPoolStatus(pool_name).execute()

                if (output.returncode == 0):
                    d = json.loads(output.stdout)
                    scan_stats = d.get('pools', {}).get(pool_name, {}).get('scan_stats', {})

                    if (scan_stats.get('function', "") == "RESILVER"):
                        if (scan_stats.get('state', "FINISHED") != "FINISHED"):
                            issued = int(scan_stats.get('issued', 0))
                            to_examine = int(scan_stats.get('to_examine', 0))

                            this._progress= int(issued/to_examine*100) if (to_examine > 0) else None
                            time.sleep(1)
                        else:
                            break
                    else:
                        break
                else:
                    error = output.stderr.decode('utf8')
                    CONFIG.error(f"Resilver state checker: {error}")
                    raise HTTPException(500,detail=ErrorMessage(code=ErrorMessages.E_POOL_SCRUB.name, params=[error]))
        except Exception as e:
            raise e

        if ((this._old_disk is not None) and (this._new_disk is not None)):
            CONFIG.replace_disk(this._old_disk, this._new_disk)
            CONFIG.flush_config()

        this._message = this.success_message
        CONFIG.info("Resilver state checker terminated successfully")