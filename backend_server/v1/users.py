from backend_server.utils.config import CONFIG
from backend_server.utils.responses import UserProfile, AccessServiceCredentials, ErrorMessage, SuccessMessage, ChgFullnameData
from backend_server.v1.auth import verify_token_factory
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Any
from nms_shared.enums import UserPermissions
from nms_shared.msg import ErrorMessages, SuccessMessages
from .auth import check_permission

verify_token = verify_token_factory()

users = APIRouter(
    prefix='/users',
    tags=['users'],
    dependencies=[Depends(verify_token)]
)

def check_user_permissions(username:str,data:Any):
    if (username != data.username):
        raise HTTPException(status_code=401)

    check_permission(username, UserPermissions.USERS_ACCOUNT_MANAGE)




@users.get("/get",response_model=Optional[UserProfile],summary="Get the information of the logged user")
def get_user(token:dict=Depends(verify_token)) -> Optional[UserProfile]:
    return CONFIG.get_user(token.get("username"))

@users.post("/set/fullname")
def set_fullname(data:ChgFullnameData,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_user_permissions(username, data)

    CONFIG.set_user_fullname(username,data.fullname)
    CONFIG.flush_config()

    return {"detail": SuccessMessage(code=SuccessMessages.S_USER_FULLNAME.name)}

@users.post("/service/{service}",summary="Change the password for a specific access service")
def change_password(service:str,credentials:AccessServiceCredentials,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_user_permissions(username,credentials)

    services = CONFIG.access_services


    if (service in services):
        s = services[service]
        if (hasattr(s,"set_password")):
            s.set_password(credentials.username,credentials.password)
        else:
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_UNKNOWN_METHOD.name))

    else:
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_ACCESS_SERV_UNK.name,params=[service]))

    return {"detail":SuccessMessage(code=SuccessMessages.S_USER_PASSWORD.name)}