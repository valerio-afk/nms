import datetime
from abc import abstractmethod
from string import Template
from nms_shared.enums import RequestMethod
import requests
from nms_shared.disks import Disk
from nms_shared.threads import NMSThread
from backend_server.utils.cmdl import ZPoolStatus, APTGetUpdate, APTGetUpgrade
from nms_shared import ErrorMessages, SuccessMessages
from backend_server.utils.responses import ErrorMessage, SuccessMessage
from fastapi import HTTPException
from typing import Optional
from urllib.parse import quote_plus
import psutil
import time
import json
import threading
import subprocess

class LongWaitThread(NMSThread):
    def __init__(this, interval:int) -> None:
        super().__init__()
        this._interval:int = interval
        this._stop_event:threading.Event = threading.Event()

    def stop(this) -> None:
        this._stop_event.set()
        super().stop()

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

class FreeOldChunkFiles(LongWaitThread):
    INTERVAL = 60*60*24 # one day

    def __init__(this,mountpoint:str):
        this._mountpoint = mountpoint


    def run(this) -> None:
        while (this.is_running):
            subprocess.run(
                ["find", this._mountpoint, "-type", "f", "-name", ".*.nms.chunk", "-mtime", "+1", "-delete"],
                stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True
            )
            if this._stop_event.wait(timeout=FreeOldChunkFiles.INTERVAL):
                break

    #

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


class DDNSServiceThread(LongWaitThread):
    DEFAULT_INTERVAL:int = 600 # 10 mins
    def __init__(this,*args,**kwargs) -> None:
        super().__init__(*args,**kwargs)
        this._last_update: Optional[int] = None
        this._next_update: Optional[int] = None

    @property
    def last_update(this) -> Optional[int]:
        return this._last_update

    @property
    def next_update(this) -> Optional[int]:
        return this._next_update


class TokenBasedDDNSThread(DDNSServiceThread):
    def __init__(this, url: str,method:RequestMethod=RequestMethod.GET,params:Optional[dict]=None,*args,**kwargs) -> None:
        super().__init__(*args,**kwargs)
        this._url = url
        this._method = method
        this._params = params

    @abstractmethod
    def _check_success(this,response:requests.Response)->bool:
        ...

    def run(this) -> None:
        from .config import CONFIG
        CONFIG.error(this._url)
        while (this.is_running):
            match (this._method):
                case RequestMethod.GET:
                    response = requests.get(this._url)
                case RequestMethod.POST:
                    response = requests.post(this._url,data=this._params)

            CONFIG.error(response.text)

            success = this._check_success(response)

            if (not success):
                raise Exception(response.text)

            this._last_update = int(datetime.datetime.now().timestamp())
            this._next_update = this._last_update + this._interval

            if this._stop_event.wait(timeout=this._interval):
                break

class DDNSNoIP(DDNSServiceThread):

    def __init__(this,userame:str,password:str,interval:int=DDNSServiceThread.DEFAULT_INTERVAL):
        super().__init__(interval=interval)
        this._username = userame
        this._password = password

    def run(this) -> None:
        while (this.is_running):
            process = subprocess.run(
                ["noip-duc", "-g", "all.ddnskey.com",
                 "--username", this._username, "--password", this._password,
                 "--once"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # optional: merge stderr into stdout
                text=True,  # decode to string
            )

            for line in process.stdout.splitlines():
                if "update failed" in line:
                    error = line.rsplit(";",1)[1]
                    raise Exception(error)
                elif "update successful" in line:
                    this._last_update = int(datetime.datetime.now().timestamp())
                    this._next_update = this._last_update + this._interval

            if this._stop_event.wait(timeout=this._interval):
                break

class DuckDNS(TokenBasedDDNSThread):
    UPDATE_ENDPOINT:Template = Template("https://www.duckdns.org/update?domains=$domain&token=$token&verbose=true&ip=")
    def __init__(this,domain:str,token:str,interval:int=DDNSServiceThread.DEFAULT_INTERVAL):
        url = DuckDNS.UPDATE_ENDPOINT.substitute(domain=quote_plus(domain),token=quote_plus(token))
        super().__init__(url,interval=interval)

    def _check_success(this,response:requests.Response)->bool:
        return (response.status_code == 200) and (response.text.strip().startswith("OK"))

class DynuDDNS(TokenBasedDDNSThread):
    UPDATE_ENDPOINT:Template = Template("http://api.dynu.com/nic/update?username=$username&password=$password")
    def __init__(this,username:str,password:str,interval:int=DDNSServiceThread.DEFAULT_INTERVAL):
        url = DynuDDNS.UPDATE_ENDPOINT.substitute(username=quote_plus(username),password=quote_plus(password))
        super().__init__(url,interval=interval)

    def _check_success(this,response:requests.Response)->bool:
        return (response.text.strip().startswith("good"))

class FreeDNS(TokenBasedDDNSThread):
    UPDATE_ENDPOINT:Template = Template("https://freedns.afraid.org/dynamic/update.php?$token")
    def __init__(this,token:str,interval:int=DDNSServiceThread.DEFAULT_INTERVAL):
        url = FreeDNS.UPDATE_ENDPOINT.substitute(token=quote_plus(token))
        super().__init__(url,interval=interval)

    def _check_success(this,response:requests.Response)->bool:
        return "Unable to locate this record" not in response.text

class DNSExit(TokenBasedDDNSThread):
    UPDATE_ENDPOINT:Template = Template("https://api.dnsexit.com/dns/ud/?apikey=$password")
    def __init__(this,username:str,password:str,interval:int=DDNSServiceThread.DEFAULT_INTERVAL):
        url = DNSExit.UPDATE_ENDPOINT.substitute(password=quote_plus(password))
        super().__init__(url,method=RequestMethod.POST,params={"host":username},interval=interval)

    def _check_success(this,response:requests.Response)->bool:
        return response.json().get("code") == 0

class Dynv6(TokenBasedDDNSThread):
    UPDATE_ENDPOINT:Template = Template("https://ipv4.dynv6.com/api/update?hostname=$domain&token=$token&ipv4=auto")
    def __init__(this,domain:str,token:str,interval:int=DDNSServiceThread.DEFAULT_INTERVAL):
        url = Dynv6.UPDATE_ENDPOINT.substitute(domain=quote_plus(domain),token=quote_plus(token))
        super().__init__(url,interval=interval)

    def _check_success(this,response:requests.Response)->bool:
        return response.status_code == 200

class ClouDNS(TokenBasedDDNSThread):
    UPDATE_ENDPOINT:Template = Template("https://ipv4.cloudns.net/api/dynamicURL/?q=$token")
    def __init__(this,token:str,interval:int=DDNSServiceThread.DEFAULT_INTERVAL):
        url = ClouDNS.UPDATE_ENDPOINT.substitute(token=quote_plus(token))
        super().__init__(url,interval=interval)

    def _check_success(this,response:requests.Response)->bool:
        return response.text.strip() == "OK"

# MTE3NTc3MzY6NzIwNDcyMTU2OjVhNzIyNjM0ZDQ1OTgxODZlYjEwNDVkMjNiZDk2ODU2ZTA3ODE3YTI5ODJiYjllYWM3ZjQ4NmYxNTEwYWU5MTY
