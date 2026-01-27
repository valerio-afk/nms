from backend_server.utils.config import CONFIG
from backend_server.utils.responses import AccessService, ErrorMessage
from nms_shared.msg import ErrorMessages
from fastapi import APIRouter, Depends, HTTPException, Request
from .auth import verify_token_factory
from typing import Dict

services = APIRouter(
    prefix='/services',
    tags=['services'],
    dependencies=[Depends(verify_token_factory())]
)



@services.get("/get",
          response_model=Dict[str,AccessService],
          responses={
              500: {"description": "Any internal error to retrieve the list of access services"},
            },
          summary="Get the list of access services"
          )
def get_system_services() -> Dict[str,AccessService]:
    try:
        return {
            k:AccessService(
                          service_name=s.service_names,
                          active=s.is_active,
                          properties= {prop:getattr(s,mtd)() for prop in s.properties if hasattr(s,mtd:=f"get_{prop}")}
                          )
            for k,s in CONFIG.access_services.items()
        }
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))


@services.post("/enable/{service}",
    responses = {500: {"description": "Any internal error while enabling an access services"}},
    summary = "Enable an access service"
)
async def enable_access_service(service: str, request: Request) -> None:
    try:
        data = await request.json()
        service = CONFIG.access_services[service]
        service.enable(**data)
    except Exception as e:
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_ACCESS_ENABLED.name,params=[service,str(e)]))

@services.post("/disable/{service}",
    responses = {500: {"description": "Any internal error while disabling an access services"}},
    summary = "Disable an access service"
)
async def disable_access_service(service: str, request: Request) -> None:
    try:
        data = await request.json()
        service = CONFIG.access_services[service]
        service.disable(**data)
    except Exception as e:
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_ACCESS_DISABLED.name,params=[service,str(e)]))