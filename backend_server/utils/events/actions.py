from .context import EventContext
from .parameters import NotificationToUser, Notification, RunScript, FileOwnership, FilePermissions, Parametrisable, P
from backend_server.utils.cmdl import Chown, Chmod
from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime
from typing import  List, Dict, Any,  Optional
import shlex
import subprocess
import os



class EventActionCategories(Enum):
    NOTIFICATION = "notification"



class ActionTags(Enum):
    SEND_TO = "send_to"
    SEND_TO_ALL = "send_to_all"
    SEND_TO_ADMINS = "send_to_admins"
    RUN_SCRIPT = "run_script"
    CHANGE_OWNER = "change_owner"
    CHANGE_PERMISSIONS = "change_permissions"

class AbstractAction(Parametrisable, ABC):
    def __init__(this, category:str,
                 tag:str,
                 context:List[EventContext],
                 event_context:Optional[List[EventContext]]=None,
                 **kwargs):
        this._tag = tag
        this._category = category
        this._context = context

        super().__init__(**kwargs)

        if (event_context is not None):
            this._context.extend(event_context)

    @property
    def tag(this):
        return this._tag

    @property
    def category(this) -> str:
        return this._category


    @property
    def context(this) -> List[EventContext]:
        return [x for x in this._context]

    @abstractmethod
    def trigger(this,parameters:P,context:Dict[str,Any]) -> None:
        ...


    def __call__(this,parameters:P,context:Dict[str,Any]) -> None:
        this.trigger(parameters=parameters,context=context)

class SendNotificationAction(AbstractAction):
    def __init__(this,tag:str,context:List[EventContext],**kwargs) -> None:
        super().__init__(category=EventActionCategories.NOTIFICATION.value,
                         tag=tag,
                         context=context,
                         **kwargs
                         )

    @staticmethod
    def _send_mail(username:str, subject:str, message:str,vars:Optional[Dict[str,str]]) -> None:
        formatted_msg = message.format_map(vars) if vars is not None else message
        formatted_subject = subject.format_map(vars) if vars is not None else subject

        cmd = ['mail', '-s', formatted_subject, username]
        subprocess.run(cmd,input=formatted_msg,text=True,capture_output=True)

class SendNotificationToAction(SendNotificationAction):
    def __init__(this,**kwargs):
        super().__init__(ActionTags.SEND_TO.value,
                         parameters=NotificationToUser,
                         context=[EventContext.TRIGGER_USER,EventContext.ISO_TIMESTAMP],
                         **kwargs
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
                            vars=context
                            )

class SendNotificationToAllAction(SendNotificationAction):
    def __init__(this, **kwargs):
        super().__init__(ActionTags.SEND_TO_ALL.value,
                         parameters=Notification,
                         context=[EventContext.TRIGGER_USER,EventContext.USER,EventContext.ISO_TIMESTAMP],
                         **kwargs
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
                                    vars=context
                                    )

class SendNotificationToAdminsAction(SendNotificationToAllAction):
    def __init__(this, **kwargs):
        super().__init__(**kwargs)
        this._tag = ActionTags.SEND_TO_ADMINS.value

    def trigger(this,parameters:P,context:Dict[str,Any]) -> None:
        admins = [ u for u in context.get(EventContext.USER.name,{})  if (hasattr(u,"admin")) and (u.admin) ]
        context.setdefault(EventContext.USER.name,admins)

        super().trigger(parameters=parameters,context=context)

class RunScriptAction(AbstractAction):
    def __init__(this,**kwargs):
        super().__init__("execution",
                         ActionTags.RUN_SCRIPT.value,
                         parameters=RunScript,
                         context=[EventContext.TRIGGER_USER, EventContext.ISO_TIMESTAMP],
                         **kwargs)

    def trigger(this,parameters:P,context:Dict[str,Any]) -> None:
        path:Optional[str] = None
        if (hasattr(parameters,"path")):
            path = parameters.path

        sudo = parameters.run_sudo if hasattr(parameters,"run_sudo") else False

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

            for k,v in context.items():
                if (k not in env):
                    env[k] = str(v)

            subprocess.run(cmd,env=env,text=True,capture_output=True)


class ChangeOwnerAction(AbstractAction):
    def __init__(this,**kwargs):
        super().__init__(
            "file",
            ActionTags.CHANGE_OWNER.value,
            parameters=FileOwnership,
            context=[
                EventContext.USER,
                EventContext.GROUP,
                EventContext.PERMISSIONS,
                EventContext.ISO_TIMESTAMP
            ],**kwargs)

    def trigger(this,parameters:P,context:Dict[str,Any]) -> None:
        if (hasattr(parameters,"path")):
            path = parameters.path.format_map(context)
        else:
            return


        if (hasattr(parameters,"user")):
            user = parameters.user.format_map(context)
        else:
            return

        group = None
        if (hasattr(parameters,"group")):
            if (len(parameters.group) > 0):
                group = parameters.group.format_map(context)

        Chown(user,group,path,sudo=True).execute()

class ChangePermissionsAction(AbstractAction):
    def __init__(this,**kwargs):
        super().__init__(
            "file",
            ActionTags.CHANGE_PERMISSIONS.value,
            parameters=FilePermissions,
            context=[
                EventContext.USER,
                EventContext.GROUP,
                EventContext.PERMISSIONS,
                EventContext.ISO_TIMESTAMP
            ],**kwargs)

    def trigger(this,parameters:P,context:Dict[str,Any]) -> None:
        if (hasattr(parameters, "path")):
            path = parameters.path.format_map(context)
        else:
            return

        if (hasattr(parameters,"permissions")):
            permissions = parameters.permissions.format_map(context)
        else:
            return

        Chmod(path,permissions,sudo=True).execute()
