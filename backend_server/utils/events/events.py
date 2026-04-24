from .actions import SendNotificationToAdminsAction, SendNotificationToAllAction, SendNotificationToAction
from .actions import  EventContext, RunScriptAction, AbstractAction
from .parameters import P, Parametrisable, TimeParameter
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

    TIMER_MINUTES = "timer.minutes"

    DISK_MOUNT = "disk.mount"
    DISK_UNMOUNT = "disk.unmount"
    USER_LOGGED_IN = "user.logged_in"
    USER_CREATED = "user.created"
    USER_DELETED = "user.deleted"
    ACCESS_ENABLED = "access.enabled"
    ACCESS_DISABLED = "access.disabled"
    VPN_ENABLED = "net.vpn_enabled"
    VPN_DISABLED = "net.vpn_disabled"

    FILE_CREATED = "file.created"
    FILE_DELETED = "file.deleted"
    FILE_MODIFIED = "file.modified"



class AbstractEvent(Parametrisable):

    def __init__(this, tag:str,
                 allowed_actions:List[AbstractAction],
                 context:Optional[List[EventContext]]=None,**kwargs):
        this._tag = tag
        this._allowed_actions = allowed_actions
        this._context = context
        super().__init__(**kwargs)


    @property
    def tag(this) -> str:
        return this._tag

    @property
    def allowed_actions(this) -> List[AbstractAction]:
        return [x for x in this._allowed_actions]

    @property
    def context(this) -> Optional[List[EventContext]]:
        return None if this._context is None else [x for x in this._context]

    def on_registration(this,uuid:str,parameters:Optional[P]=None):
        pass

    def on_unregistration(this,uuid:str):
        pass

class SystemStartupEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.SYSTEM_STARTUP.value,
                         [SendNotificationToAction(),SendNotificationToAllAction(),SendNotificationToAdminsAction(),RunScriptAction()])


class SystemRebootEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.SYSTEM_REBOOT.value,
                         [SendNotificationToAction(), SendNotificationToAllAction(), SendNotificationToAdminsAction(),
                          RunScriptAction()])


class SystemPoweroffEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.SYSTEM_POWEROFF.value,
                         [SendNotificationToAction(), SendNotificationToAllAction(), SendNotificationToAdminsAction(),
                          RunScriptAction()])

class SystemShutdownEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.SYSTEM_SHUTDOWN.value,
                         [SendNotificationToAction(), SendNotificationToAllAction(), SendNotificationToAdminsAction(),
                          RunScriptAction()])

class SystemSystemdEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.SYSTEM_SYSTEMD.value,
                         [SendNotificationToAction(), SendNotificationToAllAction(), SendNotificationToAdminsAction(),
                          RunScriptAction()])

class SystemUpdatesEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.SYSTEM_UPDATES.value,
                         [
                             SendNotificationToAction(event_context=[EventContext.PACKAGES]),
                             SendNotificationToAllAction(event_context=[EventContext.PACKAGES]),
                             SendNotificationToAdminsAction(event_context=[EventContext.PACKAGES]),
                             RunScriptAction(event_context=[EventContext.PACKAGES]),
                         ],
                         )

class SystemUpgradeEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.SYSTEM_UPGRADE.value,
                         [
                             SendNotificationToAction(event_context=[EventContext.PACKAGES]),
                             SendNotificationToAllAction(event_context=[EventContext.PACKAGES]),
                             SendNotificationToAdminsAction(event_context=[EventContext.PACKAGES]),
                             RunScriptAction(event_context=[EventContext.PACKAGES]),
                         ],
                         )


class TimerMinutesEvent(AbstractEvent):

    def __init__(this):
        from backend_server.utils.threads import CallbackThreaed
        super().__init__(
            Events.TIMER_MINUTES.value,
            [RunScriptAction()],
            parameters=TimeParameter)

        this._threads:Dict[str,CallbackThreaed] = {}

    def on_registration(this,uuid:str,parameters:Optional[P]=None) -> None:
        from backend_server.utils.threads import CallbackThreaed
        if (parameters is None) or (not hasattr(parameters,'minutes')):
            return

        interval = parameters.minutes*60


        thread = CallbackThreaed(
            timer=interval,
            callback=lambda : EVENT_MANAGER.trigger(Events.TIMER_MINUTES)
        )

        thread.start()
        this._threads[uuid] = thread

    def on_unregistration(this,uuid:str):
        if uuid not in this._threads.keys():
            thread = this._threads.pop(uuid)
            thread.stop()


class DiskMountEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.DISK_MOUNT.value,
                         [
                             SendNotificationToAction(event_context=[EventContext.PACKAGES]),
                             SendNotificationToAllAction(event_context=[EventContext.PACKAGES]),
                             SendNotificationToAdminsAction(event_context=[EventContext.PACKAGES]),
                             RunScriptAction(event_context=[EventContext.PACKAGES]),
                         ])

class DiskUnmountEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.DISK_UNMOUNT.value,
                         [SendNotificationToAction(), SendNotificationToAllAction(), SendNotificationToAdminsAction(),
                          RunScriptAction()])

class UserLoggedinEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.USER_LOGGED_IN.value,
                         [SendNotificationToAction(), SendNotificationToAllAction(), SendNotificationToAdminsAction(),
                          RunScriptAction()])

class UserCreatedEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.USER_CREATED.value,
                         [
                             SendNotificationToAction(event_context=[EventContext.ACCOUNT]),
                             SendNotificationToAllAction(event_context=[EventContext.ACCOUNT]),
                             SendNotificationToAdminsAction(event_context=[EventContext.ACCOUNT]),
                             RunScriptAction(event_context=[EventContext.ACCOUNT]),
                         ])

class UserDeletedEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.USER_DELETED.value,
                         [
                             SendNotificationToAction(event_context=[EventContext.ACCOUNT]),
                             SendNotificationToAllAction(event_context=[EventContext.ACCOUNT]),
                             SendNotificationToAdminsAction(event_context=[EventContext.ACCOUNT]),
                             RunScriptAction(event_context=[EventContext.ACCOUNT]),
                         ])

class AccessEnabledEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.ACCESS_ENABLED.value,
                         [
                             SendNotificationToAction(event_context=[EventContext.SERVICE]),
                             SendNotificationToAllAction(event_context=[EventContext.SERVICE]),
                             SendNotificationToAdminsAction(event_context=[EventContext.SERVICE]),
                             RunScriptAction(event_context=[EventContext.SERVICE]),
                         ])

class AccessDisabledEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.ACCESS_DISABLED.value,
                         [
                             SendNotificationToAction(event_context=[EventContext.SERVICE]),
                             SendNotificationToAllAction(event_context=[EventContext.SERVICE]),
                             SendNotificationToAdminsAction(event_context=[EventContext.SERVICE]),
                             RunScriptAction(event_context=[EventContext.SERVICE]),
                         ])

class VPNEnabledEvent(AbstractEvent):
    def __init__(this):
        super().__init__(Events.VPN_ENABLED.value,
                         [SendNotificationToAction(), SendNotificationToAllAction(), SendNotificationToAdminsAction(),
                          RunScriptAction()])

class VPNDisabled(AbstractEvent):
    def __init__(this):
        super().__init__(Events.VPN_DISABLED.value,
                         [SendNotificationToAction(), SendNotificationToAllAction(), SendNotificationToAdminsAction(),
                          RunScriptAction()])

class EventManager:

    __EVENT_MAPPING:Dict[str,AbstractEvent] = {
        Events.SYSTEM_STARTUP.value: SystemStartupEvent(),
        Events.SYSTEM_REBOOT.value: SystemRebootEvent(),
        Events.SYSTEM_POWEROFF.value: SystemPoweroffEvent(),
        Events.SYSTEM_SHUTDOWN.value: SystemShutdownEvent(),
        Events.SYSTEM_SYSTEMD.value: SystemSystemdEvent(),
        Events.SYSTEM_UPDATES.value: SystemUpdatesEvent(),
        Events.SYSTEM_UPGRADE.value: SystemUpgradeEvent(),
        Events.DISK_MOUNT.value: DiskMountEvent(),
        Events.DISK_UNMOUNT.value: DiskUnmountEvent(),
        Events.USER_LOGGED_IN.value: UserLoggedinEvent(),
        Events.USER_CREATED.value: UserCreatedEvent(),
        Events.USER_DELETED.value: UserDeletedEvent(),
        Events.ACCESS_ENABLED.value: AccessEnabledEvent(),
        Events.ACCESS_DISABLED.value: AccessDisabledEvent(),
        Events.VPN_ENABLED.value: VPNEnabledEvent(),
        Events.VPN_DISABLED.value: VPNDisabled(),
        Events.TIMER_MINUTES.value : TimerMinutesEvent(),
    }

    def __init__(this):
        this._registered_events:Dict[str,Any] = {e:{} for e in EventManager.__EVENT_MAPPING.keys()}
        this._triggered_actions:List[Dict[str,Any]] = []

    @property
    def events(this) -> List[AbstractEvent]:
        return [x for x in EventManager.__EVENT_MAPPING.values()]


    def register_action(this, uuid:str,
                        event_tag: str,
                        action_tag:str,
                        event_parameters:Dict[str,Any],
                        action_parameters: Dict[str, Any]
                        ) -> None:
        event:Optional[AbstractEvent] = None

        for x in this.events:
            if (x.tag == event_tag):
                event = x
                break

        if event is None:
            raise ValueError(f"Event {event_tag} not recognised")

        action = None

        for x in event.allowed_actions:
            if (x.tag == action_tag):
                action = x
                break

        if action is None:
            raise ValueError(f"Action {action_tag} not allowed in event {event_tag}")

        actions = this._registered_events[event_tag]

        action_parameter_obj = action.parameter_type(**action_parameters) if action.parameter_type is not None else None

        actions[uuid] = {
            "action": action,
            "parameters":action_parameter_obj,
        }

        event_parameter_obj = event.parameter_type(**event_parameters) if event.parameter_type is not None else None

        event.on_registration(uuid, event_parameter_obj)

    def unregister_action(this, uuid:str) -> None:
        for e,actions in this._registered_events.items():
            if (uuid in actions.keys()):
                del actions[uuid]

                for x in this.events:
                    if (x.tag == e):
                        x.on_registration(uuid)
                        break
                break


    def trigger(this, event:Events, ctx_callbacks:Optional[Dict[str,Callable[[],Any]]]=None) -> List[str]:
        triggered_actions = []
        ctx:Dict[str,Any] = {k:fn() for k,fn in ctx_callbacks.items()} if ctx_callbacks is not None else {}

        now_timestamp = datetime.datetime.now()
        ctx.setdefault(EventContext.ISO_TIMESTAMP.value, now_timestamp.isoformat())
        ctx.setdefault(EventContext.TRIGGER_USER.value, "-")

        for e,d in this._registered_events.items():
            if (e == event.value):
                for uuid,action_spec in d.items():
                    a = action_spec['action']

                    a.trigger(action_spec['parameters'],ctx)
                    triggered_actions.append({
                        "timestamp": now_timestamp.timestamp(),
                        "uuid": uuid
                    })

        this._triggered_actions.extend(triggered_actions)

        return triggered_actions

EVENT_MANAGER = EventManager()