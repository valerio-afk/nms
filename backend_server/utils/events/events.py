from .actions import SendNotificationToAdminsAction, SendNotificationToAllAction, SendNotificationToAction
from .actions import  EventContext, RunScriptAction, EventAction, ActionTags
from .actions import ACTIONS
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
import datetime



class Events(Enum):
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_REBOOT = "system.reboot"
    SYSTEM_POWEROFF = "system.poweroff"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_SYSTEMD = "system.systemd"
    SYSTEM_UPDATES = "system.updates"
    SYSTEM_UPGRADE = "system.upgrade"
    SYSTEM_NMS_UPDATES = "system.nms_updates"
    SYSTEM_NMS_UPGRADE = "system.nms_upgrade"
    SYSTEM_TIMER = "system.timer"
    DISK_MOUNT = "disk.mount"
    DISK_UNMOUNT = "disk.unmount"
    USER_LOGGED_IN = "user.logged_in"
    USER_CREATED = "user.created"
    USER_DELETED = "user.deleted"
    ACCESS_ENABLED = "access.enabled"
    ACCESS_DISABLED = "access.disabled"
    VPN_ENABLED = "net.vpn_enabled"
    VPN_DISABLED = "net.vpn_disabled"


ALLOWED_ACTIONS:Dict[Events,List[EventAction]] = {
    Events.SYSTEM_STARTUP:  [SendNotificationToAction(),SendNotificationToAllAction(),SendNotificationToAdminsAction(),RunScriptAction()],
    Events.SYSTEM_REBOOT:   [SendNotificationToAction(),SendNotificationToAllAction(),SendNotificationToAdminsAction(),RunScriptAction()],
    Events.SYSTEM_POWEROFF: [SendNotificationToAction(),SendNotificationToAllAction(),SendNotificationToAdminsAction(),RunScriptAction()],
    Events.SYSTEM_SHUTDOWN: [SendNotificationToAction(),SendNotificationToAllAction(),SendNotificationToAdminsAction(),RunScriptAction()],
    Events.SYSTEM_SYSTEMD:  [SendNotificationToAction(),SendNotificationToAllAction(),SendNotificationToAdminsAction(),RunScriptAction()],
    Events.SYSTEM_UPDATES:  [
        SendNotificationToAction(event_context=[EventContext.PACKAGES]),
        SendNotificationToAllAction(event_context=[EventContext.PACKAGES]),
        SendNotificationToAdminsAction(event_context=[EventContext.PACKAGES]),
        RunScriptAction(event_context=[EventContext.PACKAGES]),
    ],

    Events.SYSTEM_UPGRADE:  [
        SendNotificationToAction(event_context=[EventContext.PACKAGES]),
        SendNotificationToAllAction(event_context=[EventContext.PACKAGES]),
        SendNotificationToAdminsAction(event_context=[EventContext.PACKAGES]),
        RunScriptAction(event_context=[EventContext.PACKAGES]),
    ],

    Events.DISK_MOUNT:  [SendNotificationToAction(),SendNotificationToAllAction(),SendNotificationToAdminsAction(),RunScriptAction()],
    Events.DISK_UNMOUNT:  [SendNotificationToAction(),SendNotificationToAllAction(),SendNotificationToAdminsAction(),RunScriptAction()],

    Events.USER_LOGGED_IN: [SendNotificationToAction(),SendNotificationToAllAction(),SendNotificationToAdminsAction(),RunScriptAction()],
    Events.USER_CREATED: [
        SendNotificationToAction(event_context=[EventContext.ACCOUNT]),
        SendNotificationToAllAction(event_context=[EventContext.ACCOUNT]),
        SendNotificationToAdminsAction(event_context=[EventContext.ACCOUNT]),
        RunScriptAction(event_context=[EventContext.ACCOUNT]),
    ],

    Events.USER_DELETED: [
        SendNotificationToAction(event_context=[EventContext.ACCOUNT]),
        SendNotificationToAllAction(event_context=[EventContext.ACCOUNT]),
        SendNotificationToAdminsAction(event_context=[EventContext.ACCOUNT]),
        RunScriptAction(event_context=[EventContext.ACCOUNT]),
    ],


    Events.ACCESS_ENABLED:  [
        SendNotificationToAction(event_context=[EventContext.SERVICE]),
        SendNotificationToAllAction(event_context=[EventContext.SERVICE]),
        SendNotificationToAdminsAction(event_context=[EventContext.SERVICE]),
        RunScriptAction(event_context=[EventContext.SERVICE]),
    ],

    Events.ACCESS_DISABLED:  [
        SendNotificationToAction(event_context=[EventContext.SERVICE]),
        SendNotificationToAllAction(event_context=[EventContext.SERVICE]),
        SendNotificationToAdminsAction(event_context=[EventContext.SERVICE]),
        RunScriptAction(event_context=[EventContext.SERVICE]),
    ],

    Events.VPN_ENABLED:  [SendNotificationToAction(),SendNotificationToAllAction(),SendNotificationToAdminsAction(),RunScriptAction()],
    Events.VPN_DISABLED:  [SendNotificationToAction(),SendNotificationToAllAction(),SendNotificationToAdminsAction(),RunScriptAction()],
}


class EventManager:
    def __init__(this):
        this._registered_events:Dict[Events,Any] = {e:{} for e in Events}
        this._triggered_actions:List[Dict[str,Any]] = []

    def register_action(this, uuid:str, event: str,action:str,parameters:Dict[str,Any]) -> None:
        actions = this._registered_events[Events(event)]

        action_obj = ACTIONS[ActionTags(action)]()
        parameter_obj = action_obj.parameter_type(**parameters)

        actions[uuid] = {
            "action": ACTIONS[ActionTags(action)](),
            "parameters":parameter_obj,
        }

    def unregister_action(this, uuid:str) -> None:
        for e in this._registered_events.values():
            if (uuid in e.keys()):
                del e[uuid]
                break
    #
    # def get_actions(this, event:Events) -> List[EventAction]:
    #     return [x[0] for x in this._registered_events[event]]

    def trigger(this, event:Events, ctx_callbacks:Optional[Dict[str,Callable[[],Any]]]) -> List[str]:
        triggered_actions = []
        ctx:Dict[str,Any] = {k:fn() for k,fn in ctx_callbacks.items()} if ctx_callbacks is not None else {}

        now_timestamp = datetime.datetime.now()
        ctx.setdefault(EventContext.ISO_TIMESTAMP.value, now_timestamp.isoformat())
        ctx.setdefault(EventContext.TRIGGER_USER.value, "-")

        for e,d in this._registered_events.items():
            if (e == event):
                for uuid,action_spec in d.items():
                    a = action_spec['action']

                    a.trigger(action_spec['parameters'],ctx)
                    triggered_actions.append({
                        "timestamp": now_timestamp.timestamp(),
                        "uuid": uuid
                    })

        this._triggered_actions.extend(triggered_actions)

        return triggered_actions

