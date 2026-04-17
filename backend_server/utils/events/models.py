from enum import Enum
from pydantic import BaseModel, Field


class EventMetaTypes(Enum):
    NUMERIC = "numeric"
    STRING = "string"
    MULTILINE_STRING = "multiline-string"
    USER = "user"

class UserParameter(BaseModel):
    user: str =  Field(...,json_schema_extra={"metavar":"USER","metatype":EventMetaTypes.USER})


class Notification(BaseModel):
    subject:   str = Field(...,json_schema_extra={"metavar":"SUBJECT","metatype":EventMetaTypes.STRING})
    message: str = Field(...,json_schema_extra={"metavar":"MESSAGE","metatype":EventMetaTypes.STRING})


class NotificationToUser(Notification,UserParameter):
    ...