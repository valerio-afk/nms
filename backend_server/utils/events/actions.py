from .models import NotificationToUser, Notification, RunScript
from abc import ABC, abstractmethod
from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import Type, List, Dict, Any, Generic, TypeVar, Optional
import shlex
import subprocess
import os

P = TypeVar("P", bound=BaseModel)

class EventActionCategories(Enum):
    NOTIFICATION = "notification"

class EventContext(Enum):
    TRIGGER_USER = "TRIGGER_USER"
    USER = "USER"
    ISO_TIMESTAMP = "ISO_TIMESTAMP"

class ActionTags(Enum):
    SEND_TO = "send_to"
    SEND_TO_ALL = "send_to_all"
    SEND_TO_ADMINS = "send_to_admins"
    RUN_SCRIPT = "run_script"

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
        formatted_subject = subject.format_map(vars) if vars is not None else subject

        cmd = ['mail', '-s', formatted_subject, username]
        subprocess.run(cmd,input=formatted_msg,text=True,capture_output=True)

class SendNotificationToAction(SendNotificationAction):
    def __init__(this):
        super().__init__(ActionTags.SEND_TO.value,
                         NotificationToUser,
                         [EventContext.TRIGGER_USER,EventContext.ISO_TIMESTAMP]
                         )

    def trigger(this,parameters:P,context:Dict[str,Any]) -> None:
        user: Optional[str] = None
        subject: Optional[str] = None
        message: Optional[str] = None

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
                            vars={
                                EventContext.TRIGGER_USER.value:context.get(EventContext.TRIGGER_USER.value,""),
                                EventContext.ISO_TIMESTAMP.value:datetime.now().isoformat()
                            }
                            )

class SendNotificationToAllAction(SendNotificationAction):
    def __init__(this):
        super().__init__(ActionTags.SEND_TO_ALL.value,
                         Notification,
                         [EventContext.TRIGGER_USER,EventContext.USER,EventContext.ISO_TIMESTAMP]
                         )

    def trigger(this, parameters: P, context: Dict[str, Any]) -> None:
        subject:Optional[str]  = None
        message:Optional[str] = None

        if (hasattr(parameters, "subject")):
            subject = parameters.subject

        if (hasattr(parameters, "message")):
            message = parameters.message

        if ((subject is not None) and (message is not None)):
            for u in context.get(EventContext.USER.name,{}):
                if (hasattr(u,"username")):
                    this._send_mail(username=u.username,
                                    subject=subject,
                                    message=message,
                                    vars={
                                        EventContext.TRIGGER_USER.value: context.get(EventContext.TRIGGER_USER.value,""),
                                        EventContext.USER.name: u.username,
                                        EventContext.ISO_TIMESTAMP.value: datetime.now().isoformat()
                                    }
                                    )

class SendNotificationToAdminsAction(SendNotificationToAllAction):
    def __init__(this):
        super().__init__()
        this._tag = ActionTags.SEND_TO_ADMINS.value

    def trigger(this,parameters:P,context:Dict[str,Any]) -> None:
        admins = [ u for u in context.get(EventContext.USER.name,{})  if (hasattr(u,"admin")) and (u.admin) ]
        context.setdefault(EventContext.USER.name,admins)

        super().trigger(parameters=parameters,context=context)

class RunScriptAction(EventAction):
    def __init__(this):
        super().__init__("execution",ActionTags.RUN_SCRIPT.value,RunScript,[
            EventContext.TRIGGER_USER, EventContext.ISO_TIMESTAMP
        ])

    def trigger(this,parameters:P,context:Dict[str,Any]) -> None:
        path:Optional[str] = None
        if (hasattr(parameters,"path")):
            path = parameters.path

        sudo = parameters.sudo if hasattr(parameters,"sudo") else False

        if (path is not None):
            cmd:List[str] = []

            for token in shlex.split(path):
                if "=" not in token:
                    cmd.append(token)

            if (sudo):
                cmd = ["sudo"] + cmd

            env = os.environ.copy()

            env[EventContext.TRIGGER_USER.value] = context.get(EventContext.TRIGGER_USER.value,"")
            env[EventContext.ISO_TIMESTAMP.value] = datetime.now().isoformat()

            subprocess.run(cmd,env=env,text=True,capture_output=True)

ACTIONS:Dict[ActionTags,Type[EventAction]] = {
    ActionTags.SEND_TO:SendNotificationToAction,
    ActionTags.SEND_TO_ALL:SendNotificationToAllAction,
    ActionTags.SEND_TO_ADMINS:SendNotificationToAdminsAction,
    ActionTags.RUN_SCRIPT:RunScriptAction,
}