from .auth import check_permission
from backend_server.utils.cmdl import GetUserUID, RSync, Chown, Mkdir, UserDel, Chmod, GroupModChangeGroupName
from backend_server.utils.cmdl import LocalCommandLineTransaction, UserModAddGroup, GPasswdRemoveGroup, UserAdd
from backend_server.utils.cmdl import ZFSSetQuota, UserModChangeUsername, SMBPasswd, RenameFile, UserModChangeHomeDir
from backend_server.utils.config import CONFIG
from backend_server.utils.responses import ChgFullnameData, ChangeQuotaData, ChangeUsernameData, SudoData, UserDelete
from backend_server.utils.responses import NewUserProfile, WarningMessage, UserPermissionsData
from backend_server.utils.responses import UserProfile, AccessServiceCredentials, ErrorMessage, SuccessMessage
from backend_server.v1.auth import verify_token_factory
from fastapi import APIRouter, Depends, HTTPException
from nms_shared.enums import UserPermissions
from nms_shared.msg import ErrorMessages, SuccessMessages, WarningMessages
from typing import Optional, List
import os.path

verify_token = verify_token_factory()

users = APIRouter(
    prefix='/users',
    tags=['users'],
    dependencies=[Depends(verify_token)]
)

def allow_self_change(current_username:str,target_username:str):
    if (current_username!= target_username):
        check_permission(current_username, UserPermissions.USERS_ACCOUNT_MANAGE)


@users.get("/get",response_model=Optional[UserProfile],summary="Get the information of the logged user")
def get_user(token:dict=Depends(verify_token)) -> Optional[UserProfile]:
    return CONFIG.get_user(token.get("username"))

@users.get("/get/all",response_model=List[UserProfile],summary="Get the list of all users")
def get_all_users(token:dict=Depends(verify_token)) -> List[UserProfile]:
    check_permission(token.get("username"), UserPermissions.USERS_ACCOUNT_MANAGE)

    return CONFIG.users

@users.post("/set/fullname")
def set_fullname(data:ChgFullnameData,token:dict=Depends(verify_token)) -> dict:
    current_username = token.get("username")
    allow_self_change(current_username,data.username)

    CONFIG.set_user_fullname(data.username,data.fullname)
    CONFIG.flush_config()

    return {"detail": SuccessMessage(code=SuccessMessages.S_USER_FULLNAME.name)}

@users.post("/set/quota")
def set_quota(data:ChangeQuotaData,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_permission(username,UserPermissions.USERS_ACCOUNT_MANAGE)

    cmd = ZFSSetQuota(data.username,data.quota,CONFIG.pool_name,CONFIG.dataset_name,sudo=True)
    output = cmd.execute()

    if (output.returncode != 0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_USER_QUOTA.name,params=[output.stderr.strip()]))

    CONFIG.info(f"New quota set by {username} for {data.username}: {data.quota}")

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
        GroupModChangeGroupName(data.old_username,data.new_username),
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

    CONFIG.warning(f"Username change requested by {username}: {data.old_username} -> {data.new_username}")

    return {"detail": SuccessMessage(code=SuccessMessages.S_USER_NAME.name)}

@users.post("/set/sudo",summary="Add or remove a user from sudoers")
def sudoers(data:SudoData,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_permission(username,UserPermissions.USERS_ACCOUNT_MANAGE)

    cmd = UserModAddGroup(data.username,"sudo")  if (data.sudo) else GPasswdRemoveGroup(data.username,"sudo")

    output = cmd.execute()

    if (output.returncode != 0):
        HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_USER_SUDO.name,params=[output.stderr]))

    CONFIG.warning(f"Superuser status changed for {data.username} by {username}: {'Yes' if data.sudo else 'No'}")

    return {"detail":SuccessMessage(code=SuccessMessages.S_USER_SUDO.name)}

@users.post("/set/permissions",summary="Set user from permissions")
def set_permissions(data:UserPermissionsData,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_permission(username,UserPermissions.USERS_ACCOUNT_MANAGE)

    # if the user is the only admin, don't do anything
    admins = CONFIG.admins

    if ((len(admins)==1) and (admins[0].username==data.username)):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_PERM_ADMIN.name))

    CONFIG.user_set_permissions(data.username,data.permissions)
    CONFIG.flush_config()

    CONFIG.warning(f"Permission changes for {data.username} by {username}: {data.permissions}")

    return {"detail": SuccessMessage(code=SuccessMessages.S_USER_PERM.name)}

@users.post("/service/{service}",summary="Change the password for a specific access service")
def change_password(service:str,credentials:AccessServiceCredentials,token:dict=Depends(verify_token)) -> dict:
    current_username = token.get("username")
    allow_self_change(current_username,credentials.username)

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


@users.post("/new",summary="Create a new user")
def new_user(profile:NewUserProfile,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_permission(username,UserPermissions.USERS_ACCOUNT_MANAGE)

    def_groups = ['plugdev','users','netdev']

    if (UserPermissions.SERVICES_SMB_ACCESS.name in profile.permissions):
        def_groups.append('sambashare')
    if (profile.sudo):
        def_groups.append('sudo')

    allow_login = UserPermissions.SERVICES_SSH_ACCESS.name in profile.permissions
    home_dir = os.path.join(CONFIG.mountpoint,profile.username)

    cmds = [
        UserAdd(profile.username,def_groups,home_dir,allow_login),
        GetUserUID(profile.username),
        Chown(profile.username,profile.username,home_dir,['-R']),
        Chmod(home_dir,"0700", ['-R'])
    ]

    trans = LocalCommandLineTransaction(*cmds,privileged=True)
    output = trans.run()

    if (not trans.success):
        error = "\n".join([o['stderr'].strip() for o in output])
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NEW_USER.name,params=[error]) )

    uid = int(output[-1]['stdout'])

    CONFIG.add_user(profile.username,profile.visible_name,profile.permissions,uid)
    CONFIG.flush_config()

    if ((profile.quota is not None) and (len(profile.quota) > 0)):
        cmd_quota = ZFSSetQuota(profile.username,profile.quota,CONFIG.pool_name,CONFIG.dataset_name,sudo=True)

        output = cmd_quota.execute()

        if (output.returncode != 0):
            return {"detail": WarningMessage(code=WarningMessages.W_NEW_USER.name, params=[profile.username,output.stderr])}

    CONFIG.info(f"New user created by {username}: {profile.username}")

    return {"detail": SuccessMessage(code=SuccessMessages.S_NEW_USER.name,params=[profile.username])}

@users.post("/delete",summary="Delete a user")
def user_delete(data:UserDelete,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_permission(username, UserPermissions.USERS_ACCOUNT_MANAGE)

    user_to_delete = CONFIG.get_user(data.username)

    # if the user is the only admin, don't do anything
    admins = CONFIG.admins

    if ((len(admins) == 1) and (admins[0].username == data.username)):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_PERM_ADMIN.name))

    keep_home = False

    if (data.home_files == "m"):
        host_username = CONFIG.get_user(data.move_to)
        if ((host_username is not None) and (host_username.home_dir is not None)):
            src = user_to_delete.home_dir
            dest = str(os.path.join(host_username.home_dir,user_to_delete.username))

            cmds = [
                Mkdir(dest,parents=True),
                RSync(src, dest, ["-a"]),
                Chown(host_username.username, host_username.username, dest, ["-R"])
            ]

            trans = LocalCommandLineTransaction(*cmds,privileged=True)
            output = trans.run()


            if (not trans.success):
                error = "\n".join([o['stderr'].strip() for o in output])
                raise HTTPException(status_code=500,
                                    detail=ErrorMessage(code=ErrorMessages.E_USER_COPY_FILES.name,
                                                        params=[user_to_delete.username,error])
                                    )

    elif (data.home_files == "k"):
        keep_home = True

    output = UserDel(user_to_delete.username,keep_home).execute()

    if (output.returncode != 0):
        raise HTTPException(status_code=500,
                            detail=ErrorMessage(code=ErrorMessages.E_USER_DELETE.name,
                                                params=[user_to_delete.username, output.stderr])
                            )

    CONFIG.delete_user(user_to_delete.username)
    CONFIG.flush_config()

    CONFIG.info(f"User {data.username} deleted by {username}")

    return {"detail": SuccessMessage(code=SuccessMessages.S_DEL_USER.name, params=[user_to_delete.username])}


@users.post("/reset/{username}",summary="Delete a user")
def user_delete(username:str,token:dict=Depends(verify_token)) -> dict:
    admin_user = token.get("username")
    check_permission(admin_user, UserPermissions.USERS_ACCOUNT_MANAGE)

    try:
        CONFIG.reset_otp(username)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=ErrorMessage(code=ErrorMessages.E_USER_LOGIN_RESET.name,
                                                params=[username, str(e)])
                        )

    CONFIG.flush_config()

    CONFIG.warning(f"OTP reset for {username} by {admin_user}")

    return {"detail": SuccessMessage(code=SuccessMessages.S_USER_LOGIN_RESET.name, params=[username])}
