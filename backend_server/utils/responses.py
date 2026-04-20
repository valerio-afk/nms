from enum import Enum

from pydantic import BaseModel, Field, conint
from pydantic.networks import IPv4Address, IPv6Address
from typing import Optional, Any, List, Dict, Union, Literal


class InterfaceType(Enum):
    ETHERNET = 'ethernet'
    WIFI = 'wifi'
    VPN = 'vpn'
    UNKNOWN = 'unknown'

class SensorType(Enum):
    CPU = 'cpu'
    HDD = 'hdd'
    FAN = 'fan'

class SensorMetric(Enum):
    CELSIUS = '°C'
    RPM = 'RPM'


class StatusMessage(BaseModel):
    type:str
    code:str
    params: Optional[List[Any]] = None

    def __str__(this):
        return this.model_dump_json()

class ErrorMessage(StatusMessage):
    type:str = Field(default="error",frozen=True)


class WarningMessage(StatusMessage):
    type:str = Field(default="warning",frozen=True)

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

class VPNServerConf(BaseModel):
    address: IPv4Address
    netmask: IPv4Address
    endpoint: Union[IPv4Address,str]

class IPv6(BaseModel):
    enabled:bool
    dynamic: bool
    address: Optional[IPv6Address] = Field(None)
    netmask: Optional[IPv6Address] = Field(None)
    gateway: Optional[IPv6Address] = Field(None)
    dns: List[Union[str,IPv6Address]] = Field(default_factory=list)


class NetworkInterface(BaseModel):
    name:str
    enabled:bool
    ipv4: Optional[IPv4] = Field(None)
    ipv6: Optional[IPv6] = Field(None)
    network_name:Optional[str] = Field(None)
    type:InterfaceType
    has_profile: bool

class WifiNetworkInterface(NetworkInterface):
    wpa23: bool
    password: Optional[str]
    autoconnect: bool

class OTPVerification(BaseModel):
    purpose:str
    duration:int
    otp:str

class AccessService(BaseModel):
    service_name: Optional[Union[str, List[str]]]
    properties:Dict[str, Any]
    active:bool

class BackgroundTask(BaseModel):
    task_id:str
    running:bool
    progress:Optional[float]
    eta: Optional[int]
    detail:Any

class WifiNetwork(BaseModel):
    connected: bool
    bssid: str
    ssid: Optional[str] = Field(None)
    strength: int = conint(gt=0,le=4)
    security: Optional[str] = Field(None)

class WifiConnect(BaseModel):
    ssid:str
    psk:Optional[str] = Field(None)
    profile:Optional[str] = Field(None)

class VPNPeer(BaseModel):
    name:str
    public_key:str

class DDNSProvider(BaseModel):
    enabled: bool
    username:Optional[str]
    last_update:Optional[int]
    next_update:Optional[int] = Field(None)

class DDNSDefaultProviderConfiguration(BaseModel):
    username:Optional[str]
    password:str

class Quota(BaseModel):
    quota:int
    used:int

class NewUserProfile(BaseModel):
    username:str
    visible_name:Optional[str]
    permissions:List[str]
    quota:Optional[str]
    sudo:bool

class UserProfile(NewUserProfile):
    username:str
    visible_name:Optional[str]
    permissions:List[str]
    quota:Optional[Quota]
    sudo:bool
    admin:bool
    first_login_token: Optional[str] = Field(None)
    home_dir: Optional[str] = Field(None)
    uid:Optional[int] = Field(None)
    notifications:int = Field(0)

class Notification(BaseModel):
    timestamp:str
    id:str
    subject:Optional[str]
    read:bool
    body:str

class AccessServiceCredentials(BaseModel):
    username:str
    password:str

class ChangeQuotaData(BaseModel):
    username: str
    quota: Union[str,int]

class ChangeUsernameData(BaseModel):
    old_username:str
    new_username:str

class ChgFullnameData(BaseModel):
    username:str
    fullname:str

class SudoData(BaseModel):
    username:str
    sudo:bool

class Token(BaseModel):
    token:str

class AuthToken(Token):
    token:str
    username:str


class UserPermissionsData(BaseModel):
    username:str
    permissions:List[str]

class UserDelete(BaseModel):
    username:str
    home_files: Literal["k","d","m"]
    move_to: Optional[str] = Field(None)


class FileInfo(BaseModel):
    type:Literal["dir","image","video","audio","text","zip","bin","pdf","unk"]
    mimetype:Optional[str] = Field(None)
    name:str
    size:Optional[int]
    creation_time:int
    real:bool

class FSBrowse(BaseModel):
    path:str
    files:List[FileInfo]

class MkDirModel(BaseModel):
    path:str
    new_dir:str

class MvModel(BaseModel):
    old_path:str
    new_path:str

class CpModel(BaseModel):
    src:str
    dst:str

class PoolSnapshot(BaseModel):
    name:str
    ref_size:int

class CreatePool(BaseModel):
    pool_name: str
    dataset_name: str
    redundancy: bool
    encryption: bool
    compression: bool
    disks: List[str]

class ReplaceDevice(BaseModel):
    old_device: str
    new_device: str

class ImportPool(BaseModel):
    pool_name: str
    load_key:bool

class ZipFile(BaseModel):
    zip_filename: str
    files: List[str]
    format: Literal["zip","gz","xz","bz2","7z"] = Field("zip")

class Sensor(BaseModel):
    device: SensorType
    name:str
    value : Union[int,float]
    metric : SensorMetric

class SMARTPowerOnTime(BaseModel):
    hours:int
    minutes:int

class SMARTAttribute(BaseModel):
    id:int
    name:str
    value:int
    worst:int
    thresh:int
    when_failed: Any

class SMARTSelfTestLog(BaseModel):
    type:str
    status:str
    passed:bool
    progress:Optional[int]


class SMART(BaseModel):
    device:str
    available:bool
    enabled:bool
    passed:Optional[bool]
    poweron_time:Optional[SMARTPowerOnTime]
    temperature:Optional[int]
    attributes:List[SMARTAttribute]
    self_test_logs: List[SMARTSelfTestLog]


class EventSpec(BaseModel):
    event:str
    allowed_actions:List[str]

class ActionSpec(BaseModel):
    category:str
    tag:str
    parameters: Dict[str, Dict[str, str]]
    context:List[str]

class AllowedEvents(BaseModel):
    events:List[EventSpec]
    actions:List[ActionSpec]

class EventParameters(BaseModel):
    parameters:Dict[str, Any]

class RegisterEvent(EventParameters):
    event:str
    action:str

class RegisteredEvent(RegisterEvent):
    uuid:str
    enabled:bool