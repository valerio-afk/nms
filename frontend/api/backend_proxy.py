from flask import flash, session, abort
from flask_babel import _, format_datetime
from frontend.api.tasks import BackgroundTask, ResilverStatusTask
from frontend.api.threads import TimerThread
from frontend.utils.exception import NotAuthenticatedError
from nms_shared import ErrorMessages, SuccessMessages, WarningMessages
from nms_shared.disks import Disk, DiskStatus
from nms_shared.enums import LogFilter
from nms_shared.enums import RequestMethod
from nms_shared.threads import NMSThread
from requests import get, post
from requests.exceptions import HTTPError
from traceback import format_exc
from typing import Optional, List, Any, Dict, Literal, Union, Tuple
import datetime
import werkzeug.exceptions

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



def flash_once(message, category="message"):
    flashes = session.get('_flashes', [])

    if [category, message] not in flashes:
        flash(message, category)

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
            case "warning":
                msg = WarningMessages.get_warning_from_string(code, *params)
            case "success":
                msg = SuccessMessages.get_success_from_string(code,*params)
            case _:
                raise Exception(data)
    except Exception as e:
        msg = str(e) or ErrorMessages.get_error(ErrorMessages.E_UNKNOWN)
        type = "error"

    flash_once(msg,type)

unknown_response = lambda : show_flash(code=ErrorMessages.E_UNKNOWN_RESPONSE.name)

class BackEndProxy:
    TOKEN_LONGEVITY:int = 30 # 30 mins
    API = "http://localhost:8000"
    VERSION = "v1"
    TASK_LIFETIME = 60

    def __init__(this) -> None:
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
                 extra_headers:Optional[dict] = None,
                 ignore_exception:bool = False,
                 ) -> Optional[Union[bool,dict,list]]:
        url = f"{BackEndProxy.API}/{BackEndProxy.VERSION}/{endpoint}"

        if (url_params is not None):
            url += "/" + "+".join(url_params)

        headers = {}

        if (this.bearer_token is not None):
            headers["Authorization"] = "Bearer " + this.bearer_token

        if (extra_headers is not None):
            headers.update(extra_headers)

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
                    if (err.response.status_code == 401):
                        args = err.response.json()
                        abort(401,description=args)
                    if (err.response.status_code == 422):
                        error = f"URL: {err.request.url}\n"
                        error+= f"Data: {err.request.body}\n"
                        error+= f"Headers: {err.request.headers.values()}\n\n"
                        error+= f"Response: {response.raw.data}"
                        raise Exception(error)

                    err_message = err.response.json()

                    detail = err_message['detail']

                    if (
                            (isinstance(detail,str) and (detail.lower() == "not authenticated")) or
                            ((detail.get("code") == ErrorMessages.E_AUTH_REVOKED.name))
                    ):
                        raise NotAuthenticatedError()

                    make_flash(detail)
                except (RuntimeError,werkzeug.exceptions.Unauthorized) as err:
                    raise err
                except Exception as e:
                    show_flash(code=ErrorMessages.E_UNKNOWN.name)
                    flash(f"{format_exc()}\n\n{str(e)}","error")


            return None

        output = response.json()

        if ((isinstance(output,dict)) and ((flash_data:=output.get("detail")) is not None)):
            make_flash(flash_data)
            return None
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
    def tasks(this) -> List[BackgroundTask]:
        new_tasks = {}
        tasks = [t for t in this._tasks.values()]

        for task_id, task in this._tasks.items():
            this.update_task_info(task_id)
            if (task.running) and (
                    (task.last_update + NMSBACKEND.TASK_LIFETIME) >= datetime.datetime.now().timestamp()):
                new_tasks[task_id] = task

        this._tasks = new_tasks

        return tasks


    #AUTH PROPERTIES
    @property
    def is_authenticated(this) -> bool:
        if (this.bearer_token is None):
            return False

        response = get(f"{BackEndProxy.API}/{BackEndProxy.VERSION}/system/test",headers={"Authorization": "Bearer " + this.bearer_token})

        try:
            response.raise_for_status()
            return True
        except:
            return False



    @property
    def bearer_token(this) -> Optional[str]:
        return this.get_session_token("login")

    @property
    def is_otp_configured(this):
        r =  this._get_bool_property_request("auth/otp","is_configured")
        return r if r is not None else True

    # @property
    # def is_new_otp_ready(this):
    #     r = this._get_bool_property_request("auth/otp", "is_new_otp_ready")
    #     return r if r is not None else True

    # USERS PROPERTIES
    @property
    def current_user(this) -> dict:
        return this._request("users/get")

    @property
    def users(this) -> List[dict]:
        return this._request("users/get/all")




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
            uptime = r.get("uptime")
            uptime = format_datetime(uptime, "EEEE, d MMMM yyyy HH:mm").title() if uptime is not None else ""
            return {
                _('Uptime'): f"{_("Since")} {uptime}",
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
    def encryption_key(this) -> Optional[str]:
        return this._get_property_request("pool", "encryption_key")

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
        if (this.bearer_token is not None):
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
    def pool_name(this) -> Optional[str]:
        return this._get_property_request("pool", "pool_name")

    @property
    def dataset_name(this) -> Optional[str]:
        return this._get_property_request("pool", "dataset_name")


    @property
    def attachable_disks(this) -> List[Disk]:
        disks = this._request("pool/get/attachable-disks",RequestMethod.GET)
        return parse_disks_from_request(disks)

    @property
    def pool_disks(this) -> List[Disk]:
        disks = this._request("pool/get/disks", RequestMethod.GET)
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
    @property
    def network_interfaces(this) -> Optional[List[dict]]:
        r = this._request("net/ifaces",RequestMethod.GET)

        return r or []

    @property
    def vpn_config(this) -> dict:
        return this._request("net/vpn", RequestMethod.GET)

    @property
    def vpn_public_key(this) -> Optional[str]:
        return this._request("net/vpn/pubkey", RequestMethod.GET)

    @property
    def vpn_get_peers(this) -> List[Tuple[str,str]]:
        return this._request("net/vpn/peers", RequestMethod.GET)

    @property
    def vpn_public_ip(this) -> List[Tuple[str, str]]:
        return this._request("net/vpn/public-ip", RequestMethod.GET)

    @property
    def ddns_providers(this) -> Dict[str,dict]:
        return this._request("net/ddns/providers", RequestMethod.GET)

    #ACCESS SERVICES PROPERTIES
    @property
    def access_services(this) -> Dict[str,dict]:
        return this._request("services/get", RequestMethod.GET) or {}


    #AUTH METHOD
    def get_session_token(this,purpose:str) -> Optional[str]:
        try:
            return session['tokens'].get(purpose)
        except KeyError:
            return None

    def set_session_token(this,purpose:str,token:str) -> None:
        if (session.get('tokens') is None):
            session['tokens'] = {}
        session['tokens'][purpose] = token

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
            this.set_session_token("login",token)

            refresher = this._threads['token_refresher']

            if (refresher is not None):
                refresher.stop()

            refresher = TimerThread(interval=(duration-1)*60,callback=this.refresh_token)
            refresher.start()
            this._threads['token_refresher'] = refresher

            return True

        return False

    def logout(this) -> None:
        this._request("auth/logout",RequestMethod.POST)

        refresher = this._threads['token_refresher']
        this._threads['token_refresher'] = None

        if (refresher is not None):
            refresher.stop()

        session.clear()

    def refresh_token(this) -> None:
       r = this._request("auth/refresh",RequestMethod.GET)

       if (r is not None) and ((new_token := r.get("token")) is not None):
           this.set_session_token("login",new_token)

    # def reset_otp_secret(this) -> None:
    #     this._request("auth/otp/reset",RequestMethod.POST)

    def get_new_otp(this,token) -> Optional[str]:
        r = this._request("auth/otp/new",RequestMethod.GET,qstring_params={"token":token})

        if (isinstance(r, dict)):
            return r.get("provisioning_uri")

    #POOL METHODS
    def replace_disk(this,new_device:str) -> None:
        task = this._request("pool/replace",RequestMethod.POST,body_params={"old_device":new_device, "new_device":new_device})
        if isinstance(task, dict):
            this.register_task(id=task.get('task_id'),metadata="resilver",cls=ResilverStatusTask,**task)

    def pool_create(this, pool_name:str, dataset_name:str, redundancy:bool, encryption:bool, compression:bool,devs:List[str]) -> None:
        this._request("pool/create",RequestMethod.POST,body_params={
            "pool_name": pool_name,
            "dataset_name": dataset_name,
            "redundancy": redundancy,
            "encryption": encryption,
            "compression": compression,
            "disks": devs
        })

    def pool_mount(this):
        this._request("pool/mount",RequestMethod.POST)

    def pool_unmount(this):
        this._request("pool/unmount",RequestMethod.POST)

    def start_scrub(this) -> None:
        task = this._request("pool/scrub",RequestMethod.POST)

        if isinstance(task, dict):
            this.register_task(id=task.get('task_id'),metadata="scrub",**task)


    def pool_destroy(this,auth_token:str) -> None:
        this._request(
            "pool/destroy",
            RequestMethod.POST,
            extra_headers={"X-Extra-Auth-destroy":auth_token}
        )

    def simulate_format(this,auth_token:str) -> None:
        this._request(
            "pool/format",
            RequestMethod.POST,
            extra_headers={"X-Extra-Auth-format":auth_token}
        )

    def pool_recover(this, auth_token:str) -> None:
        this._request(
            "pool/recover",
            RequestMethod.POST,
            extra_headers={"X-Extra-Auth-recover":auth_token}
        )

    def pool_expand(this,new_device:str) -> Optional[Dict]:
        r = this._request("pool/expand",RequestMethod.POST,qstring_params={"new_device":new_device})

        if (isinstance(r, dict)):
            if (r.get("task_id") is not None):
                return r

    #DISK METHODS
    def format_disk(this,dev:str, auth_token:str) -> None:
        this._request(
            "disks/format",
            RequestMethod.POST,
            qstring_params={"dev":dev},
            extra_headers={"X-Extra-Auth-format-disk":auth_token}
        )

    #SERVICE METHODS
    def enable_service(this,service:str,**kwargs) -> None:
        this._request(f"services/enable/{service}",RequestMethod.POST,body_params=kwargs)

    def disable_service(this,service:str,**kwargs) -> None:
        this._request(f"services/disable/{service}",RequestMethod.POST,body_params=kwargs)

    def update_service(this,service:str,**kwargs) -> None:
        this._request(f"services/update/{service}",RequestMethod.POST,body_params=kwargs)


    #SYSTEM METHODS
    def get_logs(this,filter:LogFilter,since:Optional[int]=None,until:Optional[int]=None) -> Optional[Dict]:
        return this._request(f'system/logs/{filter.value}',RequestMethod.GET,qstring_params={"date_from":since,"date_to":until})

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

    #NETWORK METHODS
    def change_iface_status(this,iface:str,action:Union[Literal['up'],Literal['down']]) -> None:
        this._request(f"net/{iface}/{action}",RequestMethod.POST)

    def iface_up(this,iface:str) -> None:
        this.change_iface_status(iface,"up")

    def iface_down(this,iface:str) -> None:
        this.change_iface_status(iface,"down")

    def iface_setup(this, iface:str, ip_version:str, profile:str, settings:dict) -> None:
        this._request(
            f"net/{iface}/{ip_version}/config",
            RequestMethod.POST,
            qstring_params={"profile":profile},
            body_params=settings
        )

    def wifi_list(this,iface:str) -> List[Dict]:
        return this._request(f"net/{iface}/list",RequestMethod.GET)

    def wifi_connect(this,iface:str,ssid:str,psk:Optional[str],profile:Optional[str]) -> None:
        this._request(f"net/{iface}/connect",RequestMethod.POST,body_params={
            "ssid":ssid,
            "psk":psk,
            "profile":profile
        })

    def vpn_gen_keys(this) -> None:
        this._request("net/vpn/gen-keys",RequestMethod.POST)

    def vpn_change_config(this,address:str, netmask:str,endpoint:str) -> None:
        this._request(f"net/vpn/config",RequestMethod.POST,body_params={
            "address":address,
            "netmask":netmask,
            "endpoint":endpoint
        })

    def vpn_add_peer(this,name:str,public_key:str) -> None:
        this._request(f"net/vpn/peers/add",RequestMethod.POST,body_params={
            "name":name,
            "public_key":public_key
        })

    def vpn_remove_peer(this,peer:str) -> None :
        this._request(f"net/vpn/peers/remove",RequestMethod.POST,qstring_params={"name":peer})

    def ddns_enable(this,provider:str,config:Dict[str,str]) -> None:
        if ((config.get("username") is None) and (config.get("password") is None)):
            config = None

        this._request(f"net/ddns/{provider}/start",RequestMethod.POST,body_params=config)

    def ddns_disable(this,provider:str) -> None:
        this._request(f"net/ddns/{provider}/stop",RequestMethod.POST)

    #USERS METHODS

    def change_password_to_service(this,service:str,username:str,password:str) -> None:
        this._request(f"users/service/{service}",RequestMethod.POST,body_params={"username":username,"password":password})

    def set_user_fullname(this, username:str, fullname:str) -> None:
        this._request(f"users/set/fullname", RequestMethod.POST,body_params={"username": username, "fullname": fullname})

    def set_user_quota(this,username:str,quota:str) -> None:
        this._request("users/set/quota",RequestMethod.POST,body_params={"username": username, "quota": quota})

    def change_username(this,old_username:str,new_username:str) -> None:
        this._request("users/set/username",RequestMethod.POST,body_params={"old_username": old_username, "new_username": new_username})

    def set_sudo(this,username:str,sudo:bool) -> None:
        this._request("users/set/sudo",RequestMethod.POST,body_params={"username": username, "sudo": sudo})

    def set_permissions(this,username:str,permissions:List[str]) -> None:
        this._request(
            "users/set/permissions",
            RequestMethod.POST,
            body_params={"username": username, "permissions": permissions} )

    def new_user(this,username:str,fullname:str,quota:str,sudo:bool,permissions:List[str]) -> None:
        this._request("users/new",RequestMethod.POST,body_params={
            "username":username,
            "visible_name":fullname,
            "quota":quota,
            "sudo":sudo,
            "permissions":permissions
        })

    def reset_otp(this,username:str) -> None:
        this._request(f"users/reset/{username}",RequestMethod.POST)

    def delete_user(this,username:str,home_dir:str,move_to:str) -> None:
        this._request("users/delete",RequestMethod.POST,body_params={
            "username":username,
            "home_files":home_dir,
            "move_to":move_to
        })


    def verify_first_login_token(this,token:str) -> bool:
        r = this._request(f"auth/token/first_login",RequestMethod.GET,qstring_params={"token":token})

    #Other Method
    def register_task(this,
                      id:str,
                      pages:Optional[List[str]]=None,
                      metadata:Optional[str]=None,
                      cls:type[BackgroundTask]=BackgroundTask,
                      **kwargs) -> None:
        this._tasks[id] = cls(
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
        return [t for t in this.tasks if path in [p.lower() for p in t.pages]]

    def get_tasks_by_metadata(this,metadata:str) -> List[BackgroundTask]:
        return [t for t in this.tasks if metadata == t.metadata]

    def get_task_by_id(this,id:str) -> Optional[BackgroundTask]:
        for task in this.tasks:
            if (id == task.task_id):
                return task

        return None





NMSBACKEND = BackEndProxy()





























