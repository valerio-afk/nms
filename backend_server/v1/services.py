from backend_server.utils.config import CONFIG
from backend_server.utils.responses import AccessService, ErrorMessage, SuccessMessage
from nms_shared import SuccessMessages
from nms_shared.msg import ErrorMessages
from fastapi import APIRouter, Depends, HTTPException, Request
from .auth import verify_token_factory
from typing import Dict, Optional

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


@services.post("/enable/{service_id}",
    responses = {500: {"description": "Any internal error while enabling an access services"}},
    summary = "Enable an access service"
)
async def enable_access_service(service_id: str, request: Request) -> Optional[Dict]:
    try:
        data = await request.json()
        service = CONFIG.access_services[service_id]
        service.enable(**data)

        if (service.is_active):
            return {"detail":SuccessMessage(code=SuccessMessages.S_ACCESS_ENABLED.name,params=[service_id.upper()])}
        else:
            raise Exception()

    except Exception as e:
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_ACCESS_ENABLED.name,params=[service_id.upper(),str(e)]))

@services.post("/update/{service_id}",
    responses = {500: {"description": "Any internal error while disabling an access services"}},
    summary = "Update the settings in an access service"
)
async def update_access_service(service_id: str, request: Request) -> Optional[Dict]:
    try:
        data = await request.json()
        service = CONFIG.access_services[service_id]
        service.update(**data)

        return {"detail": SuccessMessage(code=SuccessMessages.S_ACCESS_UPDATED.name, params=[service_id.upper()])}

    except Exception as e:
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_ACCESS_UPDATED.name,params=[service_id.upper(),str(e)]))

@services.post("/disable/{service_id}",
    responses = {500: {"description": "Any internal error while disabling an access services"}},
    summary = "Disable an access service"
)
async def disable_access_service(service_id: str, request: Request) -> Optional[Dict]:
    try:
        data = await request.json()
        service = CONFIG.access_services[service_id]
        service.disable(**data)
        if (not service.is_active):
            return {"detail":SuccessMessage(code=SuccessMessages.S_ACCESS_DISABLED.name,params=[service_id.upper()])}
        else:
            raise Exception()
    except Exception as e:
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_ACCESS_DISABLED.name,params=[service_id.upper(),str(e)]))