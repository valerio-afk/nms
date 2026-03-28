from backend_server.utils.config import CONFIG
from backend_server.utils.responses import AccessService, ErrorMessage, SuccessMessage
from nms_shared import SuccessMessages
from nms_shared.enums import UserPermissions
from nms_shared.msg import ErrorMessages
from fastapi import APIRouter, Depends, HTTPException, Request
from .auth import verify_token_factory, check_permission
from typing import Dict, Optional


verify_token = verify_token_factory()

services = APIRouter(
    prefix='/services',
    tags=['services'],
    dependencies=[Depends(verify_token)]
)


def disable_all_access_services() -> None:
    for name, s in CONFIG.access_services.items():
        if s.is_active:
            try:
                s.disable()
            except:
                raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_ACCESS_DISABLING.name,params=[name.upper()]))

@services.get("/get",
          response_model=Dict[str,AccessService],
          responses={
              500: {"description": "Any internal error to retrieve the list of access services"},
            },
          summary="Get the list of access services"
          )
def get_system_services(token:dict=Depends(verify_token)) -> Dict[str,AccessService]:
    check_permission(token.get("username"), UserPermissions.CLIENT_DASHBOARD_SERVICES)
    # try:
    return {
        k:AccessService(
                      service_name=s.service_names,
                      active=s.is_active,
                      properties= {prop:getattr(s,mtd)() for prop in s.properties if hasattr(s,mtd:=f"get_{prop}")}
                      )
        for k,s in CONFIG.access_services.items()
    }
    # except Exception as e:
    #     raise HTTPException(status_code=500,detail=str(e))


@services.post("/enable/{service_id}",
    responses = {500: {"description": "Any internal error while enabling an access services"}},
    summary = "Enable an access service"
)
async def enable_access_service(service_id: str, request: Request,token:dict=Depends(verify_token)) -> Optional[Dict]:
    check_permission(username:=token.get("username"), UserPermissions[f"SERVICES_{service_id.upper()}_MANAGE"])
    try:
        data = await request.json()
        service = CONFIG.access_services[service_id]
        service.enable(**data)

        if (service.is_active):
            CONFIG.info(f"Access service {service_id} enabled by {username}")
            return {"detail":SuccessMessage(code=SuccessMessages.S_ACCESS_ENABLED.name,params=[service_id.upper()])}
        else:
            raise Exception()

    except HTTPException as http_e:
        raise http_e
    except Exception as e:
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_ACCESS_ENABLED.name,params=[service_id.upper(),str(e)]))

@services.post("/update/{service_id}",
    responses = {500: {"description": "Any internal error while disabling an access services"}},
    summary = "Update the settings in an access service"
)
async def update_access_service(service_id: str, request: Request, token:dict=Depends(verify_token)) -> Optional[Dict]:
    check_permission(username:=token.get("username"), UserPermissions[f"SERVICES_{service_id.upper()}_MANAGE"])
    try:
        data = await request.json()
        service = CONFIG.access_services[service_id]
        service.update(**data)

        CONFIG.info(f"Access service configuration for {service_id} changed by {username}: {data}")

        return {"detail": SuccessMessage(code=SuccessMessages.S_ACCESS_UPDATED.name, params=[service_id.upper()])}
    except HTTPException as http_e:
        raise http_e
    except Exception as e:
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_ACCESS_UPDATED.name,params=[service_id.upper(),str(e)]))

@services.post("/disable/{service_id}",
    responses = {500: {"description": "Any internal error while disabling an access services"}},
    summary = "Disable an access service"
)
async def disable_access_service(service_id: str, request: Request,token:dict=Depends(verify_token)) -> Optional[Dict]:
    check_permission(username:=token.get("username"), UserPermissions[f"SERVICES_{service_id.upper()}_MANAGE"])
    try:
        data = await request.json()
        service = CONFIG.access_services[service_id]
        service.disable(**data)
        if (not service.is_active):
            CONFIG.warning(f"Access service {service_id} disabled by {username}")
            return {"detail":SuccessMessage(code=SuccessMessages.S_ACCESS_DISABLED.name,params=[service_id.upper()])}
        else:
            raise Exception()
    except HTTPException as http_e:
        raise http_e
    except Exception as e:
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_ACCESS_DISABLED.name,params=[service_id.upper(),str(e)]))


