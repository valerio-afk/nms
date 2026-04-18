from backend_server.utils.enums import StatusAction
from backend_server.utils.config import CONFIG
from backend_server.utils.events import ALLOWED_ACTIONS, ACTIONS
from backend_server.utils.responses import AllowedEvents, EventSpec, ActionSpec
from backend_server.utils.responses import RegisterEvent, ErrorMessage, SuccessMessage, RegisteredEvent
from backend_server.v1.auth import verify_token_factory, check_permission
from fastapi import APIRouter, Depends, HTTPException
from nms_shared import ErrorMessages, SuccessMessages
from nms_shared.enums import UserPermissions
from typing import Tuple, List

verify_token = verify_token_factory()
events = APIRouter(prefix='/events',tags=['events'],dependencies=[Depends(verify_token)])


def get_all_events() -> Tuple[List[EventSpec],List[ActionSpec]]:
    events = []
    all_actions = []

    for e, actions in ALLOWED_ACTIONS.items():
        allowed_actions = []
        for a in actions:
            tag = a.value
            allowed_actions.append(tag)

            if (a not in all_actions):
                all_actions.append(a)

        events.append(EventSpec(
            event=e.value,
            allowed_actions=allowed_actions)
        )

    actions = []

    for a in all_actions:
        obj = ACTIONS[a]()
        actions.append(ActionSpec(
            category=obj.category,
            tag=a.value,
            parameters=obj.parameters,
            context=[var.value for var in obj.context],
        ))

    return events, actions

@events.get("/list", response_model=AllowedEvents,summary="Provides the list of possible events and allowed actions")
def list_events(token:dict=Depends(verify_token)) -> AllowedEvents:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_EVENTS)

    events,actions = get_all_events()


    return AllowedEvents(
        events=events,
        actions=actions,
    )

@events.get("/",summary="Get the list of registered events", response_model=List[RegisteredEvent])
def get_registered_events(token:dict=Depends(verify_token)) -> List[RegisteredEvent]:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_EVENTS)

    reg_events = CONFIG.registered_events

    return [ RegisteredEvent(
        uuid=uuid,
        event=event_data.get("name"),
        action=event_data.get("action"),
        enabled=event_data.get("enabled"),
        parameters=event_data.get("parameters"),

    ) for uuid,event_data in reg_events.items() ]


@events.post("/",summary="Register a new event")
def create_event(event:RegisterEvent,token:dict=Depends(verify_token)) -> dict:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_EVENTS)

    events, actions = get_all_events()

    # check if action is allowed in that event

    action_allowed = False
    for e in events:
        if (e.event == event.event):
            for a in e.allowed_actions:
                if (a == event.action):
                    action_allowed = True
                    break


    if (not action_allowed):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_EVENT_INVALID_ACTION.value,params=[event.action,event.event]))

    # check if the parameters are allowed for that action

    wrong_param = None

    for a in actions:
        if (a.tag == event.action):
            for p in event.parameters.keys():
                if (p not in a.parameters.keys()):
                    wrong_param = p
                    break

    if (wrong_param is not None):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_EVENT_INVALID_PARAM.value,
                                                                 params=[wrong_param, event.action]))

    CONFIG.add_event(
        event_name= event.event,
        action_name = event.action,
        **event.parameters
    )

    CONFIG.flush_config()

    return {"detail": SuccessMessage(code=SuccessMessages.S_EVENT_ADDED.name)}

@events.patch("/{uuid}/status/{action}",summary="Enable/Disable an event")
def change_event_status(uuid:str,action:StatusAction,token:dict=Depends(verify_token)) -> dict:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_EVENTS)

    match (action):
        case StatusAction.UP:
            CONFIG.enable_event(uuid)
            CONFIG.flush_config()
            return {"detail": SuccessMessage(code=SuccessMessages.S_EVENT_ENABLED.name,params=[uuid])}
        case StatusAction.DOWN:
            CONFIG.disable_event(uuid)
            CONFIG.flush_config()
            return {"detail": SuccessMessage(code=SuccessMessages.S_EVENT_DISABLED.name, params=[uuid])}

@events.delete("/{uuid}",summary="Delete an event")
def delete_event(uuid:str,token:dict=Depends(verify_token)) -> dict:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_EVENTS)
    CONFIG.delete_event(uuid)
    CONFIG.flush_config()

    return {"detail": SuccessMessage(code=SuccessMessages.S_EVENT_DELETED.name, params=[uuid])}