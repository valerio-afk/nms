from enum import Enum
from pydantic import BaseModel, Field


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
