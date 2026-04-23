from backend_server.utils.enums import StatusAction
from backend_server.utils.config import CONFIG
from backend_server.utils.responses import  EventSpec, ActionSpec, EventParameters
from backend_server.utils.responses import RegisterEvent, ErrorMessage, SuccessMessage, RegisteredEvent
from backend_server.v1.auth import verify_token_factory, check_permission
from fastapi import APIRouter, Depends, HTTPException

from backend_server.utils.events import EVENT_MANAGER
from nms_shared import ErrorMessages, SuccessMessages
from nms_shared.enums import UserPermissions
from typing import  List

verify_token = verify_token_factory()
events = APIRouter(prefix='/events',tags=['events'],dependencies=[Depends(verify_token)])


def get_all_events() -> List[EventSpec]:
    events = []

    for event in EVENT_MANAGER.events:
        allowed_actions =[]

        for action in event.allowed_actions:
            allowed_actions.append(
                ActionSpec(
                    category=action.category,
                    tag=action.tag,
                    parameters=action.parameters,
                    context=[var.value for var in action.context],
                )
            )

        events.append(EventSpec(
            event=event.tag,
            allowed_actions=allowed_actions)
        )

    return events

@events.get("/list", response_model=List[EventSpec],summary="Provides the list of possible events and allowed actions")
def list_events(token:dict=Depends(verify_token)) -> List[EventSpec]:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_EVENTS)

    return get_all_events()


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

    events = get_all_events()

    # check if action is allowed in that event

    action_allowed = None
    for e in events:
        if (e.event == event.event):
            for a in e.allowed_actions:
                if (a.tag == event.action):
                    action_allowed = a
                    break


    if (action_allowed is None):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_EVENT_INVALID_ACTION.value,params=[event.action,event.event]))

    # check if the parameters are allowed for that action

    wrong_param = None

    for p in event.parameters.keys():
        if (p not in action_allowed.parameters.keys()):
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

@events.patch("/{uuid}",summary="Update event parameters")
def delete_event(uuid:str,parameters:EventParameters,token:dict=Depends(verify_token)) -> dict:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_EVENTS)

    try:
        CONFIG.update_event_parameters(uuid,parameters.parameters)
        CONFIG.flush_config()
    except AttributeError:
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_EVENT_INVALID.value))
    except KeyError as e:
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_EVENT_INVALID_PARAM.value,
                                                                 params=[str(e), uuid]))

    return {"detail": SuccessMessage(code=SuccessMessages.S_EVENT_UPDATED.name, params=[uuid])}

@events.delete("/{uuid}",summary="Delete an event")
def delete_event(uuid:str,token:dict=Depends(verify_token)) -> dict:
    check_permission(token.get("username"), UserPermissions.SYS_ADMIN_EVENTS)
    CONFIG.delete_event(uuid)
    CONFIG.flush_config()

    return {"detail": SuccessMessage(code=SuccessMessages.S_EVENT_DELETED.name, params=[uuid])}