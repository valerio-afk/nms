from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, TypeVar, Type, Dict,Generic

P = TypeVar("P", bound=BaseModel)

class Parametrisable(Generic[P]):
    def __init__(this,parameters:Optional[Type[P]]=None):
        this._parameters = parameters

    @property
    def parameter_type(this) -> Optional[Type[P]]:
        return this._parameters

    @property
    def parameters(this) -> Dict[str,Dict[str, str]]:
        return {
            name: {
                "metavar": field.json_schema_extra.get("metavar", None),
                "metatype": field.json_schema_extra.get("metatype", None),
            } for name,field in this._parameters.model_fields.items()
        } if this._parameters is not None else {}


class EventMetaTypes(Enum):
    NUMERIC = "numeric"
    STRING = "string"
    BOOL = "bool"
    MULTILINE_STRING = "multiline-string"
    USER = "user"

class UserParameter(BaseModel):
    user: str =  Field(...,json_schema_extra={"metavar":"USER","metatype":EventMetaTypes.USER})


class Notification(BaseModel):
    subject:   str = Field(...,json_schema_extra={"metavar":"SUBJECT","metatype":EventMetaTypes.STRING})
    message: str = Field(...,json_schema_extra={"metavar":"MESSAGE","metatype":EventMetaTypes.STRING})


class NotificationToUser(Notification,UserParameter):
    ...

class PathParameter(BaseModel):
    path:str = Field(...,json_schema_extra={"metavar":"PATH","metatype":EventMetaTypes.STRING})

class RunScript(PathParameter):
    run_sudo: bool = Field(...,json_schema_extra={"metavar":"SUDO","metatype":EventMetaTypes.BOOL})

class FileOwnership(UserParameter):
    group:Optional[str]

class FilePermissions(BaseModel):
    permissions:int

class TimeParameter(BaseModel):
    minutes:int = Field(...,json_schema_extra={"metavar":"MINUTES","metatype":EventMetaTypes.NUMERIC})