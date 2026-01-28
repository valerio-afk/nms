from enum import Enum
from flask import flash
from flask_babel import _

from frontend.exception import NotAuthenticatedError
from nms_shared import ErrorMessages
from nms_shared.disks import Disk, DiskStatus
from requests import get, post
from requests.exceptions import HTTPError
from typing import Optional, List, Any, Dict



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

    try:
        match type:
            case "error":
                msg = ErrorMessages.get_error_from_string(code,*params)
            case _:
                raise Exception("Wrong Error code")
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

    def __init__(this) -> None:
        this._bearer:Optional[str] = None

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
                    err_message = err.response.json()

                    detail = err_message['detail']

                    if (isinstance(detail,str) and (detail.lower() == "not authenticated")):
                        raise NotAuthenticatedError()

                    make_flash(detail)
                except RuntimeError as err:
                    raise err
                except Exception as e:
                    show_flash(code=ErrorMessages.E_UNKNOWN.name)
                    flash(str(e),"error")

            return None

        return response.json()

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


    #AUTH PROPERTIES
    @property
    def is_otp_configured(this):
        return this._get_bool_property_request("auth/otp","is_configured")

    #ACCESS SERVICES
    @property
    def access_services(this) -> List[dict]:
        r = this._request("services/get",RequestMethod.GET)

        return r or []

    #POOL PROPERTIES
    @property
    def is_pool_configured(this) -> bool:
        return this._get_bool_property_request("pool", "is_pool_configured")

    @property
    def pool_settings(this) -> Dict[str, bool]:
        tag = "pool"

        return {
            _("Encryption") : this._get_bool_property_request(tag,"encryption"),
            _("Redundancy"): this._get_bool_property_request(tag, "redundancy"),
            _("Compression"): this._get_bool_property_request(tag, "compression")
        }

    #DISK PROPERTIES
    def get_disks(this) -> List[Disk]:
        disks = this._request("disks/get/disks",RequestMethod.GET)

        if (disks is not None):
            return [
                Disk(
                    name = disk.get("name"),
                    model=disk.get("model"),
                    serial=disk.get("serial"),
                    size = disk.get("size"),
                    status = DiskStatus(disk.get("status")),
                    path = disk.get("path")
                ) for disk in disks
            ]

        return []


    #POOL PROPERTIES
    @property
    def pool_status_id(this) -> Optional[str]:
        if (this._bearer is not None):
            return this._get_property_request("pool","status_id")
        return None

    #NET PROPERTIES
    def iface_status(this) -> Optional[List[dict]]:
        r = this._request("net/iface",RequestMethod.GET)

        if (r is not None):
            return r.get("status")

        return None


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
        token = this.verify_otp(otp)
        if (token is not None):
            this._bearer = token
            return True

        return False







NMSBACKEND = BackEndProxy()





























