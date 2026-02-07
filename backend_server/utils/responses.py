from pydantic import BaseModel, Field
from pydantic.networks import IPv4Address, IPv6Address
from typing import Optional, Any, List, Dict, Union
from datetime import timedelta

class StatusMessage(BaseModel):
    type:str
    code:str
    params: Optional[List[Any]] = None

    def __str__(this):
        return this.model_dump_json()

class ErrorMessage(StatusMessage):
    type:str = Field(default="error",frozen=True)


class SuccessMessage(StatusMessage):
    type:str = Field(default="success",frozen=True)


class ExpasionStatus(BaseModel):
    is_running: bool
    eta: Optional[int]
    progress: Optional[float]

class BackendProperty(BaseModel):
    property:str
    value: Any

class NetCounter(BaseModel):
    bytes_sent: Optional[int]
    bytes_recv: Optional[int]

class IPv4(BaseModel):
    dynamic: bool
    address: Optional[IPv4Address] = Field(None)
    netmask: Optional[IPv4Address] = Field(None)
    gateway: Optional[IPv4Address] = Field(None)
    dns: List[Union[str,IPv4Address]] = Field(default_factory=list)

class IPv6(BaseModel):
    enabled:bool
    address: Optional[IPv6Address] = Field(None)
    netmask: Optional[IPv6Address] = Field(None)
    gateway: Optional[IPv6Address] = Field(None)
    dns: List[Union[str,IPv6Address]] = Field(default_factory=list)


class NetworkInterface(BaseModel):
    name:str
    enabled:bool
    ipv4: Optional[IPv4]
    ipv6: Optional[IPv6]
    network_name:Optional[str]

class WifiNetworkInterface(NetworkInterface):
    wpa23: bool
    password: Optional[str]
    autoconnect: bool

class OTPVerification(BaseModel):
    purpose:str
    duration:int
    otp:str

class AccessService(BaseModel):
    service_name: Union[str, List[str]]
    properties:Dict[str, Any]
    active:bool

class BackgroundTask(BaseModel):
    task_id:str
    running:bool
    progress:Optional[float]
    eta: Optional[int]
    detail:Any

