import datetime
from enum import Enum
from flask import flash
from flask_babel import _
from traceback import format_exc

from frontend.api.tasks import BackgroundTask
from frontend.api.threads import TimerThread
from frontend.exception import NotAuthenticatedError
from nms_shared import ErrorMessages, SuccessMessages
from nms_shared.disks import Disk, DiskStatus
from requests import get, post
from requests.exceptions import HTTPError
from typing import Optional, List, Any, Dict, Literal, Union

from nms_shared.threads import NMSThread

def parse_disks_from_request(d:Optional[List[dict]]) -> List[Disk]:
    if (d is not None):
        return [
            Disk(
                name=disk.get("name"),
                model=disk.get("model"),
                serial=disk.get("serial"),
                size=disk.get("size"),
                status=DiskStatus(disk.get("status")),
                path=disk.get("path")
            ) for disk in d
        ]

    return []


def show_flash(type:str="error", code:str=ErrorMessages.E_UNKNOWN.name,params:List[Any]=None) -> None:
    make_flash(
        {
            "type":type,
            "code":code,
            "params": params if params is not None else []
        }
    )

def make_flash(data:dict) -> None:
    type = data.get("type")
    code = data.get("code")
    params = data.get("params") or []

    msg = ""

    try:
        match type:
            case "error":
                msg = ErrorMessages.get_error_from_string(code,*params)
            case "success":
                msg = SuccessMessages.get_success_from_string(code,*params)
            case _:
                raise Exception(data)
    except Exception as e:
        msg = str(e) or ErrorMessages.get_error(ErrorMessages.E_UNKNOWN)
        type = "error"

    flash(msg,type)

unknown_response = lambda : show_flash(code=ErrorMessages.E_UNKNOWN_RESPONSE.name)

class RequestMethod(Enum):
    GET = "GET"
    POST = "POST"

class BackEndProxy:
    TOKEN_LONGEVITY:int = 30 # 30 mins
    API = "http://localhost:8000"
    VERSION = "v1"
    TASK_LIFETIME = 60

    def __init__(this) -> None:
        this._bearer:Optional[str] = None
        this._tasks:Dict[str, BackgroundTask] = {}
        this._threads:Dict[str,Optional[NMSThread]] = {
            'token_refresher' : None
        }

    def _request(this,
                 endpoint:str,
                 method:RequestMethod = RequestMethod.GET,
                 url_params:Optional[List[str]] = None,
                 qstring_params:Optional[dict] = None,
                 body_params:Optional[dict] = None,
                 ignore_exception:bool = False,
                 ) -> Optional[dict]:
        url = f"{BackEndProxy.API}/{BackEndProxy.VERSION}/{endpoint}"

        if (url_params is not None):
            url += "/" + "+".join(url_params)

        headers = {}

        if (this._bearer is not None):
            headers["Authorization"] = "Bearer " + this._bearer

        match method:
            case RequestMethod.GET:
                fn = get
            case RequestMethod.POST:
                fn = post

        req_params = {}

        if (qstring_params is not None):
            req_params["params"] = qstring_params
        if (body_params is not None):
            req_params["json"] = body_params
            headers["Content-Type"] = "application/json"

        req_params["headers"] = headers

        response = fn(url, **req_params)

        try:
            response.raise_for_status()
        except HTTPError as err:
            if (not ignore_exception):
                try:
                    if (err.response.status_code == 422):
                        error = f"URL: {err.request.url}\n"
                        error+= f"Data: {err.request.body}\n"
                        error+= f"Headers: {err.request.headers.values()}\n\n"
                        error+= f"Response: {response.raw.data}"
                        raise Exception(error)

                    err_message = err.response.json()

                    detail = err_message['detail']

                    if (isinstance(detail,str) and (detail.lower() == "not authenticated")):
                        raise NotAuthenticatedError()

                    make_flash(detail)
                except RuntimeError as err:
                    raise err
                except Exception as e:
                    show_flash(code=ErrorMessages.E_UNKNOWN.name)
                    flash(f"{format_exc()}\n\n{str(e)}","error")


            return None

        output = response.json()

        if ((isinstance(output,dict)) and ((flash_data:=output.get("detail")) is not None)):
            make_flash(flash_data)
        else:
            return output

    def _get_property_request(this, tag:str, property:str) -> Any:
        endpoint = f"{tag}/get"

        result = this._request(endpoint, RequestMethod.GET, [property])

        if (isinstance(result, dict)):
            try:
                server_property = result['property']
                value = result['value']

                if (server_property == property):
                    return value
                else:
                    raise Exception()
            except Exception:
                unknown_response()

    def _get_bool_property_request(this, tag:str, property:str,coerce_to:bool=False) -> bool:
        r = this._get_property_request(tag, property)

        return r if isinstance(r, bool) else coerce_to

    #OTHER PROPERTIES
    @property
    def tasks(this) -> List:
        return []


    #AUTH PROPERTIES
    @property
    def is_otp_configured(this):
        return this._get_bool_property_request("auth/otp","is_configured")


    #SYSTEM PROPERTIES
    @property
    def last_apt_time(this) -> Optional[datetime.datetime]:
        dt = this._get_property_request("system","last_apt_time")

        return datetime.datetime.fromtimestamp(dt) if dt is not None else None

    @property
    def system_updates(this) -> List[str]:
        return this._get_property_request("system","system_updates") or []

    @property
    def system_information(this) -> Dict[str,Any]:
        r = this._get_property_request("system","system_information")

        if (r is not None):
            return {
                _('Uptime'): f"{_("Since")} {r.get('uptime',"")}",
                _('NMS Version'): r.get('nms_ver',""),
                _('CPU'): r.get('cpu',""),
                _('OS'): r.get('os',""),
                "_cpu_load": f"{r.get("cpu_load","")}",
                "_memory_load": f"{r.get("memory_load", "")}",
                '_net_counters': r.get("net_counters",{})
            }

        return {}

    #POOL PROPERTIES
    @property
    def scrub_report(this) -> Optional[Dict[str, str]]:
        return this._get_property_request("pool", "last_scrub_report")

    @property
    def scrub_info(this) -> Dict[str, Any]:
        return this._get_property_request("pool", "scrub_info")

    @property
    def importable_pools(this) -> List[dict]:
        return this._get_property_request("pool", "pool_list") or []

    @property
    def pool_status_id(this) -> Optional[str]:
        if (this._bearer is not None):
            return this._get_property_request("pool", "status_id")
        return None

    @property
    def is_pool_configured(this) -> bool:
        return this._get_bool_property_request("pool", "is_configured")

    @property
    def is_mounted(this) -> bool:
        return this._get_bool_property_request("pool", "is_mounted")

    @property
    def pool_capacity(this) -> Optional[Dict[str,int]]:
        return this._get_property_request("pool", "pool_capacity")

    @property
    def mountpoint(this) -> Optional[str]:
        return this._get_property_request("pool", "mountpoint")

    @property
    def pool_settings_raw(this) -> Dict[str, bool]:
        return this._get_property_request("pool", "pool_settings") or {}

    @property
    def pool_settings(this) -> Dict[str, bool]:
        settings = this._get_property_request("pool", "pool_settings")

        return {
            _("Encryption") : settings.get("encryption",False),
            _("Redundancy"): settings.get("redundancy",False),
            _("Compression"):settings.get("compression",False),
        }

    @property
    def has_encryption(this) -> bool:
        return this.pool_settings_raw.get("encryption",False)



    @property
    def attachable_disks(this) -> List[Disk]:
        disks = this._request("pool/get/attachable-disks",RequestMethod.GET)
        return parse_disks_from_request(disks)


    #DISK PROPERTIES
    @property
    def disks(this) -> List[Disk]:
        disks = this._request("disks/get/disks",RequestMethod.GET)
        return parse_disks_from_request(disks)

    @property
    def system_disks(this) -> List[Disk]:
        disks = this._request("disks/get/sys-disks", RequestMethod.GET)
        return parse_disks_from_request(disks)


    #NET PROPERTIES
    def iface_status(this) -> Optional[List[dict]]:
        r = this._request("net/ifaces",RequestMethod.GET)

        return r or []

    #ACCESS SERVICES PROPERTIES
    @property
    def access_services(this) -> Dict[str,dict]:
        return this._request("services/get", RequestMethod.GET) or {}

    #AUTH METHOD
    def verify_otp(this,otp:str,purpose:str="login",duration:int=TOKEN_LONGEVITY) -> Optional[str]:
        data = {
            "otp": otp,
            "purpose": purpose,
            "duration": duration
        }

        r = this._request("auth/otp/verify", RequestMethod.POST, body_params=data)

        if (r is None):
            return None

        if ((token := r.get("token")) is not None):
            return token
        else:
            unknown_response()

    def login(this, otp:str) -> bool:
        duration = BackEndProxy.TOKEN_LONGEVITY
        token = this.verify_otp(otp)
        if (token is not None):
            this._bearer = token

            refresher = this._threads['token_refresher']

            if (refresher is not None):
                refresher.stop()

            refresher = TimerThread(interval=(duration-1)*60,callback=this.refresh_token)
            refresher.start()
            this._threads['token_refresher'] = refresher


            return True

        return False

    def refresh_token(this) -> None:
       r = this._request("auth/refresh",RequestMethod.GET)

       if (r is not None) and ((new_token := r.get("token")) is not None):
           this._bearer = new_token

    #SERVICE
    def enable_service(this,service:str,**kwargs) -> None:
        this._request(f"services/enable/{service}",RequestMethod.POST,body_params=kwargs)

    def disable_service(this,service:str,**kwargs) -> None:
        this._request(f"services/disable/{service}",RequestMethod.POST,body_params=kwargs)

    def update_service(this,service:str,**kwargs) -> None:
        this._request(f"services/update/{service}",RequestMethod.POST,body_params=kwargs)


    #SYSTEM METHODS
    def shutdown(this) -> None:
        this._request("system/shutdown",RequestMethod.POST)

    def restart(this) -> None:
        this._request("system/restart",RequestMethod.POST)

    def restart_systemd_services(this) -> None:
        this._request("system/restart-systemd-services",RequestMethod.POST)

    def apt_get(this,action:Union[Literal['update'],Literal['upgrade']]) -> Optional[Dict]:
        r = this._request(f"system/apt/{action}", RequestMethod.POST)

        return r if isinstance(r,dict) else None

    def apt_get_update(this) -> Optional[Dict]:
        return this.apt_get("update")

    def apt_get_upgrade(this) -> Optional[Dict]:
        return this.apt_get("upgrade")

    #Other Method
    def register_task(this,id:str,pages:Optional[List[str]]=None,metadata:Optional[str]=None,**kwargs) -> None:
        this._tasks[id] = BackgroundTask(
            pages=pages,
            last_update=datetime.datetime.now().timestamp(),
            metadata=metadata,
            **kwargs)

    def update_task_info(this,task_id:str) -> None:

        task = this._tasks.get(task_id)

        if (task is not None):
            r = this._request(f"system/task/{task_id}",RequestMethod.GET)
            task.last_update = datetime.datetime.now().timestamp()

            if (r is None):
                task.running = False
                task.eta = None
                task.progress = None
            else:
                task.running = r.get("running",False)
                task.progress = r.get("progress")
                task.eta = r.get("eta")



    def get_tasks_by_path(this,path:str) -> List[BackgroundTask]:
        path = path.lower()
        new_tasks = {}
        tasks = []

        for task_id,task in this._tasks.items():
            if (path in [p.lower() for p in task.pages]):
                this.update_task_info(task_id)
                tasks.append(task)

            if (task.running) and ((task.last_update+NMSBACKEND.TASK_LIFETIME) >= datetime.datetime.now().timestamp()):
                new_tasks[task_id] = task

        this._tasks = new_tasks

        return tasks






NMSBACKEND = BackEndProxy()





























