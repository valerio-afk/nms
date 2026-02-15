from .auth import check_permission
from backend_server.utils.cmdl import LocalCommandLineTransaction, UserModAddGroup, GPasswdRemoveGroup
from backend_server.utils.cmdl import ZFSSetQuota, UserModChangeUsername, SMBPasswd, RenameFile, UserModChangeHomeDir
from backend_server.utils.config import CONFIG
from backend_server.utils.responses import ChgFullnameData, ChangeQuotaData, ChangeUsernameData, SudoData
from backend_server.utils.responses import UserProfile, AccessServiceCredentials, ErrorMessage, SuccessMessage
from backend_server.v1.auth import verify_token_factory
from fastapi import APIRouter, Depends, HTTPException
from nms_shared.enums import UserPermissions
from nms_shared.msg import ErrorMessages, SuccessMessages
from typing import Optional, Any, List
import os.path

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

@users.get("/get/all",response_model=List[UserProfile],summary="Get the list of all users")
def get_all_users(token:dict=Depends(verify_token)) -> List[UserProfile]:
    check_permission(token.get("username"), UserPermissions.USERS_ACCOUNT_MANAGE)

    return CONFIG.users

@users.post("/set/fullname")
def set_fullname(data:ChgFullnameData,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_user_permissions(username, data)

    CONFIG.set_user_fullname(username,data.fullname)
    CONFIG.flush_config()

    return {"detail": SuccessMessage(code=SuccessMessages.S_USER_FULLNAME.name)}

@users.post("/set/quota")
def set_quota(data:ChangeQuotaData,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_user_permissions(username, data)

    cmd = ZFSSetQuota(data.username,data.quota,CONFIG.pool_name,CONFIG.dataset_name,sudo=True)
    output = cmd.execute()

    if (output.returncode != 0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_USER_QUOTA.name,params=[output.stderr.strip()]))


    return {"detail": SuccessMessage(code=SuccessMessages.S_USER_QUOTA.name)}

@users.post("/set/username")
def set_username(data:ChangeUsernameData,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_permission(username, UserPermissions.USERS_ACCOUNT_MANAGE)

    old_homedir = os.path.join(CONFIG.mountpoint,data.old_username)
    new_homedir = os.path.join(CONFIG.mountpoint, data.new_username)

    SMBPasswd(data.old_username, flag=SMBPasswd.Flags.DELETE).execute() #if this step fails, it's ok - we dont know if this user had smb

    cmds = [
        UserModChangeUsername(data.old_username,data.new_username),
        RenameFile(old_homedir,new_homedir),
        UserModChangeHomeDir(data.new_username,old_homedir,new_homedir),
    ]

    trans = LocalCommandLineTransaction(*cmds,privileged=True)
    output = trans.run()

    if (not trans.success):
        errors = "\n".join([o['stderr'].strip() for o in output])
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_USER_QUOTA.name,params=[errors]))

    CONFIG.change_username(data.old_username,data.new_username)
    CONFIG.flush_config()

    return {"detail": SuccessMessage(code=SuccessMessages.S_USER_NAME.name)}

@users.post("/set/sudo",summary="Add or remove a user from sudoers")
def sudoers(data:SudoData,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_user_permissions(username,data)

    cmd = UserModAddGroup(data.username,"sudo")  if (data.sudo) else GPasswdRemoveGroup(data.username,"sudo")

    output = cmd.execute()

    if (output.returncode != 0):
        HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_USER_SUDO.name,params=[output.stderr]))

    return {"detail":SuccessMessage(code=SuccessMessages.S_USER_SUDO.name)}

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

