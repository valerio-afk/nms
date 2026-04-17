from .models import NotificationToUser, Notification
from abc import ABC, abstractmethod
from enum import Enum
from pydantic import BaseModel
from typing import Type, List, Dict, Any, Generic, TypeVar, Optional
import subprocess

P = TypeVar("P", bound=BaseModel)

class EventActionCategories(Enum):
    NOTIFICATION = "notification"

class EventContext(Enum):
    TRIGGER_USER = "TRIGGER_USER"
    ALL_USERS = "ALL_USERS"
    ISO_TIMESTAMP = "ISO_TIMESTAMP"

class EventAction(Generic[P],ABC):
    def __init__(this,category:str,tag:str,parameters:Type[P],context:List[EventContext]):
        this._tag = tag
        this._category = category
        this._parameters = parameters
        this._context = context

    @property
    def tag(this):
        return this._tag

    @property
    def category(this) -> str:
        return this._category

    @property
    def parameter_type(this) -> Type[P]:
        return this._parameters

    @property
    def parameters(this) -> Dict[str,Dict[str, str]]:
        return {
            name: {
                "metavar": field.json_schema_extra.get("metavar", None),
                "metatype": field.json_schema_extra.get("metatype", None),
            } for name,field in this._parameters.model_fields.items()
        }

    @property
    def context(this) -> List[EventContext]:
        return [x for x in this._context]

    @abstractmethod
    def trigger(this,parameters:P,context:Dict[str,Any]) -> None:
        ...

    def __call__(this,parameters:P,context:Dict[str,Any]) -> None:
        this.trigger(parameters=parameters,context=context)

class SendNotificationAction(EventAction):
    def __init__(this,tag:str,parameters:Type[P],context:List[EventContext]) -> None:
        super().__init__(category=EventActionCategories.NOTIFICATION.value,
                         tag=tag,
                         parameters=parameters,
                         context=context
                         )

    @staticmethod
    def _send_mail(username:str, subject:str, message:str,vars:Optional[Dict[str,str]]) -> None:
        formatted_msg = message.format_map(vars) if vars is not None else message

        cmd = ['mail', '-s', subject, username]
        subprocess.run(cmd,input=formatted_msg,text=True,capture_output=True)

class SendNotificationToAction(SendNotificationAction):
    def __init__(this):
        super().__init__("send_to",
                         NotificationToUser,
                         [EventContext.TRIGGER_USER,EventContext.ISO_TIMESTAMP]
                         )

    def trigger(this,parameters:P,context:Dict[str,Any]) -> None:
        user = subject = message = None

        if (hasattr(parameters,"user")):
            user = parameters.user

        if (hasattr(parameters,"subject")):
            subject = parameters.subject

        if (hasattr(parameters,"message")):
            message = parameters.message

        if ((user is not None) and (subject is not None) and (message is not None)):
            this._send_mail(username=user,
                            subject=subject,
                            message=message,
                            vars={EventContext.TRIGGER_USER.name:context.get(EventContext.TRIGGER_USER.name)}
                            )

class SendNotificationToAllAction(SendNotificationAction):
    def __init__(this):
        super().__init__("send_to_all",
                         Notification,
                         [EventContext.TRIGGER_USER,EventContext.ALL_USERS,EventContext.ISO_TIMESTAMP]
                         )

    def trigger(this, parameters: P, context: Dict[str, Any]) -> None:
        user = subject = message = None

        if (hasattr(parameters, "user")):
            user = parameters.user

        if (hasattr(parameters, "subject")):
            subject = parameters.subject

        if (hasattr(parameters, "message")):
            message = parameters.message

        if ((user is not None) and (subject is not None) and (message is not None)):

            for u in context.get(EventContext.ALL_USERS.name,{}):
                if (hasattr(u,"username")):
                    this._send_mail(username=user,
                                    subject=subject,
                                    message=message,
                                    vars={EventContext.TRIGGER_USER.name: context.get(
                                        EventContext.TRIGGER_USER.name)}
                                    )

class SendNotificationToAdminsAction(SendNotificationToAllAction):
    def __init__(this):
        super().__init__()
        this._tag = "send_to_admins"

    def trigger(this,parameters:P,context:Dict[str,Any]) -> None:
        admins = [ u for u in context.get(EventContext.ALL_USERS.name,{})  if (hasattr(u,"admin")) and (u.admin) ]
        context.setdefault(EventContext.ALL_USERS.name,admins)

        super().trigger(parameters=parameters,context=context)





