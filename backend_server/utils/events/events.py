from .actions import P
from .actions import SendNotificationToAction, SendNotificationToAllAction, SendNotificationToAdminsAction, EventAction
from enum import Enum
from typing import List, Dict, Any, Type, Tuple



class Events(Enum):
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_REBOOT = "system.reboot"
    SYSTEM_RESTART = "system.poweroff"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_SYSTEMD = "system.systemd"
    SYSTEM_UPDATES = "system.updates"
    SYSTEM_UPGRADE = "system.upgrade"
    SYSTEM_NMS_UPDATES = "system.nms_updates"
    SYSTEM_NMS_UPGRADE = "system.nms_upgrade"
    DISK_MOUNT = "disk.mount"
    DISK_UNMOUNT = "disk.unmount"
    USER_LOGGED_IN = "user.logged_in"
    USER_CREATED = "user.created"
    USER_DELETED = "user.deleted"
    ACCESS_ENABLED = "access.enabled"
    ACCESS_DISABLED = "access.disabled"
    VPN_ENABLED = "vpn.enabled"
    VPN_DISABLED = "vpn.disabled"


ALLOWED_ACTIONS:Dict[Events,List[Type[EventAction]]] = {
    Events.SYSTEM_STARTUP: [SendNotificationToAction,SendNotificationToAllAction,SendNotificationToAdminsAction],
    Events.SYSTEM_REBOOT: [SendNotificationToAction,SendNotificationToAllAction,SendNotificationToAdminsAction],
    Events.SYSTEM_RESTART: [SendNotificationToAction,SendNotificationToAllAction,SendNotificationToAdminsAction],
    Events.SYSTEM_SHUTDOWN: [SendNotificationToAction,SendNotificationToAllAction,SendNotificationToAdminsAction],
}


class EventManager:
    def __init__(this):
        this._registered_events = {e:[] for e in Events}

    def register_action(this, event: Events,action:EventAction,parameters:P) -> None:
        actions = this._registered_events[event]
        actions.append((action,parameters))

    def get_actions(this, event:Events) -> List[EventAction]:
        return [x[0] for x in this._registered_events[event]]

    def trigger(this, action:EventAction, ctx:Dict[str,Any]) -> List[Tuple[Events,EventAction]]:
        triggered_actions = []
        for e,(a,p) in this._registered_events.items():
            if (a == action):
                a.trigger(p,ctx)
                triggered_actions.append((e,a))

        return triggered_actions

