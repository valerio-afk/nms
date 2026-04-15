from enum import Enum
from typing import List, Dict, Any
from utils.events.actions import SendNotificationToAction, SendNotificationToAllAction, SendNotificationToAdminsAction
from utils.events.actions import EventAction, P


class Events(Enum):
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_REBOOT = "system.reboot"
    SYSTEM_RESTART = "system.poweroff"
    SYSTEM_SHUTDOWN = "system.shutdown"

ALLOWED_ACTIONS = {
    Events.SYSTEM_STARTUP: [SendNotificationToAction,SendNotificationToAllAction,SendNotificationToAdminsAction],
    Events.SYSTEM_REBOOT: [SendNotificationToAction,SendNotificationToAllAction,SendNotificationToAdminsAction],
    Events.SYSTEM_RESTART: [SendNotificationToAction,SendNotificationToAllAction,SendNotificationToAdminsAction],
    Events.SYSTEM_SHUTDOWN: [SendNotificationToAction,SendNotificationToAllAction,SendNotificationToAdminsAction],
}


class EventManager:
    def __init__(this):
        this._registered_events = { e:[] for e in Events}

    def register_action(this, event: Events,action:EventAction,parameters:P) -> None:
        actions = this._registered_events[event]
        actions.append((action,parameters))

    def get_actions(this, event:Events) -> List[EventAction]:
        return [x[0] for x in this._registered_events[event]]

    def trigger(this, action:EventAction, ctx:Dict[str,Any]) -> None:
        for e,(a,p) in this._registered_events.items():
            if (a == action):
                a.trigger(p,ctx)

