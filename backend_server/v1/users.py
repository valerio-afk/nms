import datetime
import subprocess
from .auth import check_permission
from backend_server.utils.cmdl import LocalCommandLineTransaction, UserModAddGroup, GPasswdRemoveGroup, Stat, Cat
from backend_server.utils.cmdl import RSync, Chown, Mkdir, UserDel, GroupModChangeGroupName, GetEntShadow, GetEntPasswd
from backend_server.utils.cmdl import ZFSSetQuota, UserModChangeUsername, SMBPasswd, RenameFile, UserModChangeHomeDir
from backend_server.utils.config import CONFIG, create_system_user
from backend_server.utils.events import EventContext, Events
from backend_server.utils.responses import ChgFullnameData, ChangeQuotaData, ChangeUsernameData, SudoData, UserDelete
from backend_server.utils.responses import NewUserProfile, WarningMessage, UserPermissionsData, Notification
from backend_server.utils.responses import UserProfile, AccessServiceCredentials, ErrorMessage, SuccessMessage
from backend_server.v1.auth import verify_token_factory
from dataclasses import  dataclass
from fastapi import APIRouter, Depends, HTTPException, Response
from nms_shared.enums import UserPermissions
from nms_shared.msg import ErrorMessages, SuccessMessages, WarningMessages
from requests.structures import CaseInsensitiveDict
from typing import Optional, List
from email.utils import parsedate_to_datetime
import os.path
import re

verify_token = verify_token_factory()

users = APIRouter(
    prefix='/users',
    tags=['users'],
    dependencies=[Depends(verify_token)]
)

def allow_self_change(current_username:str,target_username:str):
    if (current_username!= target_username):
        check_permission(current_username, UserPermissions.USERS_ACCOUNT_MANAGE)

@dataclass
class MBoxMail:
    From:str
    date:datetime.datetime
    headers:CaseInsensitiveDict[str]
    id:str
    body:str

def get_mbox_basepath():
    return "/var/mail"

def get_mail_number(username:str) -> int:
    MAIL_BASEPATH = get_mbox_basepath()
    mail_file = os.path.join(MAIL_BASEPATH,username)
    stat = Stat(mail_file,sudo=True).execute()

    n_mails = 0

    if (stat is not None) and ((stat.returncode == 0)):
        cat = Cat(mail_file,sudo=True).execute()

        if (cat is not None) and ((cat.returncode == 0)):
            pattern = re.compile(r"^From[^:](.*)$")
            for l in cat.stdout.splitlines():
                if (pattern.match(l) is not None):
                    n_mails+=1
                elif ("X-Notification-Read" in l):
                    k,v = l.strip().split(":")
                    if (int(v.strip()) == 1):
                        n_mails-=1

    return n_mails

def parse_mbox(username:str) -> List[MBoxMail]:
    MAIL_BASEPATH = get_mbox_basepath()
    mail_file = os.path.join(MAIL_BASEPATH, username)
    stat = Stat(mail_file, sudo=True).execute()

    mail = []

    if (stat is not None) and ((stat.returncode == 0)):
        cat = Cat(mail_file, sudo=True).execute()

        if (cat is not None) and ((cat.returncode == 0)):
            current_mail = {}
            last_header = None

            pattern_begin = re.compile(r"^From [a-zA-Z0-9_-]+(@[a-zA-Z0-9_\-.]+)?\s+(.*)$")
            pattern_header = re.compile(r"^([a-zA-Z0-9_-]+):\s*(.*)$")
            pattern_header_cnt = re.compile(r"^(\s+)(.*)$")
            pattern_msg_id = re.compile(r"^\s*<([0-9a-zA-Z.-]+)(@(.+))?>\s*$")
            body_started = False

            for l in cat.stdout.splitlines():

                if (match := pattern_begin.match(l)):
                    body_started = False
                    if (len(current_mail) > 0):
                        current_mail['body'] = current_mail['body'].strip()
                        mail.append(MBoxMail(**current_mail))

                    date = match.group(2)
                    current_mail = {
                        "date": parsedate_to_datetime(date),
                        "From": l.strip()
                    }
                    continue

                if (not body_started):

                    if (match := pattern_header.match(l)):
                        hdr = match.group(1)
                        value = match.group(2)

                        if (hdr.lower() == "message-id"):
                            if (id_match := pattern_msg_id.match(value)):
                                current_mail["id"] = id_match.group(1)
                        elif (hdr.lower() == "date"):
                            current_mail['date'] = parsedate_to_datetime(value)

                        if (current_mail.get("headers") is None):
                            current_mail['headers'] = CaseInsensitiveDict({hdr: value})
                        else:
                            current_mail['headers'][hdr] = value

                        last_header = hdr
                    if  (match:=pattern_header_cnt.match(l)):
                        current_mail['headers'][last_header]+=match.group(0)
                    if (len(l.strip())==0):
                        body_started = True
                        current_mail['body'] = ""
                else:
                    current_mail["body"]+=f"\n{l}"

            if (len(current_mail) > 0):
                current_mail['body'] = current_mail['body'].strip()
                mail.append(MBoxMail(**current_mail))

    return mail

def mail2notification(mail:MBoxMail) -> Notification:
    read_header = mail.headers.get("X-Notification-Read", "0")
    return Notification(
        timestamp=mail.date.isoformat(),
        id=mail.id,
        subject=mail.headers.get("Subject"),
        read=True if ((read_header is not None) and (read_header == "1")) else False,
        body=mail.body,
    )

def flush_mailbox(username:str,mbox:List[MBoxMail]) -> None:
    file = ""

    for mail in mbox:
        file+=mail.From + "\n"
        for k,v in mail.headers.items():
            file+=f"{k}: {v}\n"
        file+=f"\n{mail.body}\n\n"

    MAIL_BASEPATH = get_mbox_basepath()
    mail_file = os.path.join(MAIL_BASEPATH, username)

    subprocess.run(
        ["sudo", "tee", mail_file],
        input=file,
        text=True,
        stdout=subprocess.DEVNULL,
        check=True
    )

    Chown(username,"mail",mail_file,sudo=True).execute()

@users.get("/get",response_model=Optional[UserProfile],summary="Get information of the logged user")
def get_user(token:dict=Depends(verify_token)) -> Optional[UserProfile]:
    return CONFIG.get_user(token.get("username"))

@users.head("/get/notifications",summary="Retrieves the notification count the logged user")
def get_user_notifications_count(token:dict=Depends(verify_token)) -> Response:
    n = get_mail_number(token.get("username"))

    return Response(
        status_code=200,
        headers={"X-User-Notifications-Count": str(n)},
    )

@users.delete("/get/notifications/{notification_id}",summary="Delete the given notification from the logged user")
def delete_user_notification(notification_id=str,token:dict=Depends(verify_token)) -> None:
    username:Optional[str] = token.get("username")

    if (username is not None):
        mbox = parse_mbox(username)
        idx = None

        for i,mail in enumerate(mbox):
            if (mail.id == notification_id):
                idx = i

        if (idx is not None):
            del mbox[idx]
            flush_mailbox(username,mbox)



@users.get("/get/notifications",response_model=List[Notification],summary="Retrieves the notifications of the logged user")
def get_user_notifications(token:dict=Depends(verify_token)) -> List[Notification]:
    notifications : List[Notification] = []
    username:Optional[str] = token.get("username")

    if (username is not None):
        mbox = parse_mbox(username)

        for mail in mbox:
            notifications.append(
                mail2notification(mail)
            )

    notifications.sort(key=lambda x : x.timestamp,reverse=True)

    return notifications

@users.get("/get/notifications/{notification_id}",response_model=Optional[Notification],summary="Get the specified notification for the logged user")
def get_user_notification(notification_id:str,token:dict=Depends(verify_token)) -> Optional[Notification]:
    username:Optional[str] = token.get("username")

    found = None

    if (username is not None):
        mbox = parse_mbox(username)
        for mail in mbox:
            if (mail.id == notification_id):
                found = mail2notification(mail)
                mail.headers['X-Notification-Read'] = "1"
                break

        flush_mailbox(username,mbox)

    return found


@users.get("/get/sys",response_model=List[str],summary="Get the list of system usernames that have not been associated to other user")
def get_available_system_users(token:dict=Depends(verify_token)):
    username = token.get("username")
    check_permission(username, UserPermissions.USERS_ACCOUNT_MANAGE)

    nms_users = CONFIG.users
    used_uid = [uid for x in nms_users if (uid:=x.uid) is not None]

    cmd = GetEntPasswd().execute()

    if (cmd.returncode!=0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_USER_SYSTEM.name,params=[cmd.stderr]))

    system_users = []

    for u in cmd.stdout.splitlines():
        tokens = u.split(":")
        uid = int(tokens[2])
        if ((uid not in used_uid) and (uid>=1000)):
            system_users.append(tokens[0])

    return system_users

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

    cmd = GetEntShadow(data.old_username).execute()
    out = cmd.stdout

    if (len(out) == 0):
        u = CONFIG.get_user(data.old_username)
        if (u is None):
            raise HTTPException(status_code=500,
                          detail=ErrorMessage(code=ErrorMessages.E_USER_NOT_FOUND.name, params=[data.username]))

        create_system_user(data.new_username, u.permissions, u.sudo)
    else:
        cmds = [
            UserModChangeUsername(data.old_username,data.new_username),
            GroupModChangeGroupName(data.old_username, data.new_username),
        ]

        trans = LocalCommandLineTransaction(*cmds, privileged=True)
        output = trans.run()

        if (not trans.success):
            errors = "\n".join([o['stderr'].strip() for o in output])
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_USER_NAME.name, params=[errors]))

        SMBPasswd(data.old_username,flag=SMBPasswd.Flags.DELETE).execute()  # if this step fails, it's ok - we dont know if this user had smb

    mountpoint = CONFIG.mountpoint

    if (mountpoint is not None):
        old_homedir = os.path.join(mountpoint,data.old_username)
        new_homedir = os.path.join(mountpoint, data.new_username)

        if(old_homedir!=new_homedir):
            cmds = [
                RenameFile(old_homedir,new_homedir),
                UserModChangeHomeDir(data.new_username,old_homedir,new_homedir),
            ]

            trans = LocalCommandLineTransaction(*cmds,privileged=True)
            output = trans.run()

            if (not trans.success):
                errors = "\n".join([o['stderr'].strip() for o in output])
                raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_USER_NAME.name,params=[errors]))

    CONFIG.change_username(data.old_username,data.new_username)
    CONFIG.flush_config()

    CONFIG.warning(f"Username change requested by {username}: {data.old_username} -> {data.new_username}")

    return {"detail": SuccessMessage(code=SuccessMessages.S_USER_NAME.name)}

@users.post("/set/sys-user",summary="Assign a specific system user (Unix) to the given user (their username will be renamed)")
def assign_system_user(data:ChangeUsernameData,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_permission(username, UserPermissions.USERS_ACCOUNT_MANAGE)

    CONFIG.change_username(data.old_username, data.new_username)
    CONFIG.flush_config()

    CONFIG.warning(f"System user {data.new_username} assigned to {data.old_username} by {username}")

    return {"detail": SuccessMessage(code=SuccessMessages.S_USER_NAME.name)}



@users.post("/set/sudo",summary="Add or remove a user from sudoers")
def sudoers(data:SudoData,token:dict=Depends(verify_token)) -> dict:
    username = token.get("username")
    check_permission(username,UserPermissions.USERS_ACCOUNT_MANAGE)

    cmd = GetEntShadow(data.username).execute()
    out = cmd.stdout

    add_sudo = data.sudo

    if (len(out)==0):
        u = CONFIG.get_user(data.username)
        if (u is None):
            raise HTTPException(status_code=500,
                          detail=ErrorMessage(code=ErrorMessages.E_USER_NOT_FOUND.name, params=[data.username]))

        create_system_user(data.username,u.permissions,add_sudo)

    else:
        cmd = UserModAddGroup(data.username,CONFIG.sudo_group)  if (data.sudo) else GPasswdRemoveGroup(data.username,CONFIG.sudo_group)

        output = cmd.execute()

        if (output.returncode != 0):
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_USER_SUDO.name,params=[output.stderr]))

    CONFIG.warning(f"Superuser status changed for {data.username} by {username}: {'Yes' if add_sudo else 'No'}")

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
            cmd = GetEntShadow(credentials.username).execute()

            out = cmd.stdout

            if (len(out)==0):
                u = CONFIG.get_user(credentials.username)
                if (u is None):
                    raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_USER_NOT_FOUND.name,params=[credentials.username]))

                create_system_user(credentials.username,u.permissions,u.sudo)


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

    try:
        uid = create_system_user(profile.username,profile.permissions,profile.sudo)
    except Exception as e:
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NEW_USER.name,params=[str(e)]) )


    CONFIG.add_user(profile.username,profile.visible_name,profile.permissions,uid)
    CONFIG.flush_config()

    if ((profile.quota is not None) and (len(profile.quota) > 0)):
        cmd_quota = ZFSSetQuota(profile.username,profile.quota,CONFIG.pool_name,CONFIG.dataset_name,sudo=True)

        output = cmd_quota.execute()

        if (output.returncode != 0):
            return {"detail": WarningMessage(code=WarningMessages.W_NEW_USER.name, params=[profile.username,output.stderr])}

    CONFIG.info(f"New user created by {username}: {profile.username}")
    CONFIG.trigger_event(Events.USER_CREATED, {EventContext.ACCOUNT.value: profile.username})

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
    CONFIG.trigger_event(Events.USER_DELETED, {EventContext.ACCOUNT.value: data.username})

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
