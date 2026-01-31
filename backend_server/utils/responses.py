from pydantic import BaseModel, Field
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
    eta: Optional[timedelta]
    progress: Optional[float]

class BackendProperty(BaseModel):
    property:str
    value: Any

class NetCounter(BaseModel):
    bytes_sent: Optional[int]
    bytes_recv: Optional[int]

class NetworkInterface(BaseModel):
    name:str
    status:bool
    ipv4: Optional[str]
    ipv6: Optional[str]
    network_name:Optional[str]

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

