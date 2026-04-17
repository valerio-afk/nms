from backend_server.utils.events import ALLOWED_ACTIONS
from backend_server.utils.responses import AllowedEvents, EventSpec, ActionSpec
from fastapi import APIRouter

events = APIRouter(prefix='/events',tags=['events'])

@events.get("/list", response_model=AllowedEvents,summary="Provides the list of possible events and allowed actions")
def list_events() -> AllowedEvents:
    events = []
    all_actions = []

    for e,actions in ALLOWED_ACTIONS.items():
        allowed_actions = []
        for a in actions:
            obj = a()
            tag = obj.tag
            allowed_actions.append(tag)

            if (a not in all_actions):
                all_actions.append(a)

        events.append(EventSpec(
            event=e,
            allowed_actions=allowed_actions)
        )

    actions = []

    for a in all_actions:
        obj = a()
        actions.append(ActionSpec(
            category=obj.category,
            tag=obj.tag,
            parameters=obj.parameters,
            context=obj.context,
        ))

    return AllowedEvents(
        events=events,
        actions=actions,
    )