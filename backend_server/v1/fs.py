from PIL import Image
from backend_server.utils.cmdl import Chown, Chmod, LocalCommandLineTransaction, LS, Stat, MimeType, Mkdir, Move, ALS
from backend_server.utils.cmdl import RemoveFile, Touch, SetfACL, Zip, Unpack, TarArchive, SevenZip, Copy, MD5Sum, Truncate
from backend_server.utils.config import CONFIG, SECRET_KEY
from backend_server.utils.events import Events, EventContext
from backend_server.utils.inet import get_local_ips
from backend_server.utils.responses import ErrorMessage, UserProfile, FileInfo, FSBrowse, MkDirModel, MvModel, Quota
from backend_server.utils.responses import ZipFile, CpModel, SharedFileInfo, FileSharing, SharedFile
from backend_server.v1.auth import verify_token_factory, check_permission, create_token, token_verification, bearer
from datetime import datetime,timedelta, UTC
from email.utils import format_datetime
from fastapi import HTTPException, APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.security import  HTTPBearer
from fastapi.security import HTTPAuthorizationCredentials
from io import BytesIO
from nms_shared import ErrorMessages
from nms_shared.enums import UserPermissions
from pathlib import Path
from typing import Optional, List, Generator, Dict, Any, Tuple
from urllib.parse import urlparse
import base64
import grp
import hashlib
import httpx
import ipaddress
import jwt
import os
import pwd
import pytz
import re
import subprocess


verify_token = verify_token_factory()
permissive_bearer = HTTPBearer(auto_error=False)


def verify_onlyoffice_token(token: str):
    try:
        payload = jwt.decode(
            token,
            CONFIG.ONLYOFFICE_CONF['jwt_secret'],
            algorithms=["HS256"]
        )
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid ONLYOFFICE token")

def verify_onlyoffice(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    token = credentials.credentials
    return verify_onlyoffice_token(token)

def verify_user_token_shared_files(credentials:HTTPAuthorizationCredentials = Depends(permissive_bearer)) -> Optional[Dict[str,Any]]:
    if (credentials is None):
        return None

    token = credentials.credentials
    try:
        return token_verification(token,"login")
    except HTTPException as e:
        return None

def verify_shared_file_token(token:str):
    requested_purpose = "fileshare"
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms="HS256")

        purpose = payload.get("purpose")
        if (purpose is None):
            CONFIG.error("Token missing `purpose` claim")
            raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_MALFORMED.name))
        elif (purpose != requested_purpose):
            CONFIG.error(f"Purpose claim not matching ({purpose} != {requested_purpose})")
            raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_INVALID.name))

        path = payload.get("path")
        share_info = CONFIG.get_share_information(path)


        if (share_info is None):
            raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_EXPIRED.name))

        payload['token'] = token

        return payload

    except jwt.PyJWTError:
        raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_MALFORMED.name))

fs = APIRouter(
    prefix='/fs',
    tags=['fs'],
    dependencies=[Depends(verify_token)]
)

fs_preview = APIRouter(
    prefix='/fs',
    tags=['fs']
)

onlyoffice = APIRouter(
    prefix='/onlyoffice',
    tags=['onlyoffice']
)

file_sharing = APIRouter(
    prefix='/filesharing',
    tags=['filesharing'],
    dependencies=[Depends(verify_user_token_shared_files), Depends(verify_shared_file_token)]
)

TUS_VERSION = "1.0.0"




def check_path_jail(user:UserProfile,path:str,stat_last:bool=True) -> Path:
    home = Path(user.home_dir)
    requested_path = home.joinpath(path).resolve()

    if (not requested_path.is_relative_to(home)):
        raise HTTPException(status_code=401)

    current = Path(user.home_dir)

    parts = requested_path.relative_to(home).parts

    for i,part in enumerate(parts):
        current = current.joinpath(part)

        stat = Stat(str(current),"%N\n%F",sudo=True).execute()

        if (stat.returncode!=0):
            if (i<(len(parts)-1) or ((i==(len(parts)-1)) and stat_last)):
                raise HTTPException(status_code=401,detail=f"Cannot stat `{current}`")
            else:
                continue

        fname,type = stat.stdout.splitlines()

        if (type.strip().lower() == "symbolic link"):
            _, real_path = fname.split("->")
            target = Path(real_path.strip("'"))
            if not (target.is_relative_to(home)):
                raise HTTPException(status_code=401)

    return requested_path


def check_shared_path(path: str, username: Optional[str] = None) -> Optional[Path]:
    fullpath = (Path(CONFIG.mountpoint) / path).resolve()
    share_info = CONFIG.get_share_information(str(fullpath))

    if (share_info is None):
        return None

    share_with = share_info.get("share_with", None)

    if ((share_with is not None) and (username not in share_with.keys())):
        return None

    return fullpath

def shared_file_check_authorisation(
        filename:str,
        authentication_token:Optional[Dict[str,Any]],
        anon_user_token:Optional[str] = None
) -> Tuple[Path,bool]:
    #
    # Resolve authenticated user (if any)
    #
    user = None

    if authentication_token is not None:
        user = CONFIG.get_user(authentication_token.get("username"))

    #
    # Get all shares available to this user.
    #
    # include_all=True means:
    # - user-specific shares
    # - public shares
    #

    shared_with_user = CONFIG.get_files_shared_with(
        None if user is None else user.username,
        include_all=True
    )

    CONFIG.flush_config()

    #
    # Resolve mountpoint to avoid path traversal and
    # path representation inconsistencies.
    #
    mountpoint = Path(CONFIG.mountpoint).resolve()

    #
    # Resolve the requested path.
    #
    # IMPORTANT:
    # resolve() normalizes:
    # - ../
    # - symlinks
    # - duplicate separators
    #
    requested_path = Path(mountpoint, filename).resolve()

    #
    # Ensure requested path stays inside mountpoint.
    #
    # Prevents:
    # /browse/../../etc/passwd
    #
    if not requested_path.is_relative_to(mountpoint):
        raise HTTPException(status_code=403)

    #
    # These variables represent:
    #
    # matched_shared_root:
    #   The share boundary that grants access.
    #
    # matched_share_data:
    #   ACL/configuration associated with the share.
    #
    matched_shared_root = None
    matched_share_data = None

    can_edit = False

    #
    # Find which shared root authorizes this request.
    #
    # IMPORTANT:
    # We preserve the ORIGINAL shared root.
    # We do NOT replace it with the requested path.
    #
    for shared_path, share_data in shared_with_user.items():

        shared_root = Path(shared_path).resolve()

        if requested_path.is_relative_to(shared_root):

            #
            # Prefer the MOST SPECIFIC matching share.
            #
            # Example:
            #
            # /a
            # /a/private
            #
            # If accessing /a/private/file.txt,
            # we should use /a/private.
            #
            if (
                    matched_shared_root is None or
                    len(shared_root.parts) > len(matched_shared_root.parts)
            ):
                matched_shared_root = shared_root
                matched_share_data = share_data

    #
    # No matching share found.
    #
    if matched_shared_root is None:
        raise HTTPException(status_code=403)

    #
    # Resolve edit permissions for authenticated users.
    #
    if user is not None:

        user_acl = matched_share_data.get("share_with", {}).get(
            user.username
        )

        if user_acl is not None:
            can_edit = user_acl.get("can_edit", False)

    #
    # Anonymous users must present a valid anonymous share token.
    #
    if user is None:

        if anon_user_token is None:
            raise HTTPException(status_code=403)

        anon_token_data = verify_shared_file_token(anon_user_token)

        #
        # Token contains the path it grants access to.
        #
        granted_path = anon_token_data.get("path")

        if granted_path is None:
            raise HTTPException(status_code=403)

        granted_path = Path(granted_path).resolve()

        #
        # Ensure the requested file is inside the granted path.
        #
        # This preserves your inheritance model:
        #
        # If /a is shared,
        # then /a/subdir/file.txt is also allowed.
        #
        if not requested_path.is_relative_to(granted_path):
            raise HTTPException(status_code=403)

        #
        # Additional safety:
        #
        # Ensure token does not grant MORE than the matched share.
        #
        # Example:
        #
        # Token grants /a
        # but request matched /a/private
        #
        # This prevents mismatched share scopes.
        #
        if not granted_path.is_relative_to(matched_shared_root):
            raise HTTPException(status_code=403)

    return requested_path, can_edit


def change_permissions(path:str,group:str="users") -> None:
    if (not CONFIG.is_mounted):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_UNMOUNTED.name))

    cmds = [
        Chown(None,group, path,['-R'],True),
        Chmod(path,"770",["-R"],True)
    ]

    trans = LocalCommandLineTransaction(*cmds)
    output = trans.run()

    if (not trans.success):
        errors = "\n ".join([x["stderr"] for x in output])
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_FS_CH_PERM.name, params=[path,errors]))

def change_ownership(path:str) -> None:
    account = CONFIG.access_account

    try:
        uid = pwd.getpwnam(account.get("username","")).pw_uid
        gid = grp.getgrnam(account.get("group","")).gr_gid

        cmd = Chown(uid,gid,path,sudo=True)
        output = cmd.execute()

        if (output.returncode != 0):
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_FS_CH_PERM.name, params=[path, output.stderr]))

    except Exception as e:
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_FS_CH_PERM.name, params=[path, str(e)]))


def file_generator_dd(path:str,chunk_size:Optional[int]=1024**2, start:int=0,end:Optional[int]=None) -> Generator[bytes, None, None]:
    proc = subprocess.Popen(
        ["sudo","dd", f"if={path}", "status=none","iflag=skip_bytes",f"skip={start}"],
        stdout=subprocess.PIPE
    )

    delta = None if end is None else (end-start+1)

    if (chunk_size is None):
        if (end is None):
            chunk_size=1024**2
        else:
            chunk_size=end-start+1

    while True:
        if ((delta is not None) and (delta<=0)):
            break

        read_size = chunk_size if delta is None else min(chunk_size,delta)
        chunk = proc.stdout.read(read_size)

        if (not chunk):
            break

        if (delta is not None):
            delta -= len(chunk)

        yield chunk

def file_generator(path: str, chunk_size:int=1024**2, start: int = 0, end:Optional[int] = None) -> Generator[bytes, None, None]:
    with open(path, "rb") as f:
        f.seek(start)

        remaining = None if end is None else (end - start + 1)

        while True:
            read_n_bytes = chunk_size if remaining is None else min(chunk_size, remaining)
            chunk = f.read(read_n_bytes)

            if not chunk:
                break

            if remaining is not None:
                remaining -= len(chunk)

            yield chunk

            if remaining is not None and remaining <= 0:
                break

def get_file_info(path:str) -> Optional[FileInfo]:
    stat = Stat(path, "%n\n%s\n%F\n%W\n%y\n%U",sudo=True).execute()

    if (stat.returncode == 0):
        fullpath, size, ftype, creation_time,modification_time,owner = (
            stat.stdout.splitlines())

        fname = os.path.split(path)[1]

        match (ftype):
            case "directory":
                ftype = "dir"
                mime_type = "inode/directory"
            case "regular file" | "regular empty file":
                mime_type_cmd = MimeType(path,sudo=True).execute()
                ftype = "bin"
                mime_type = "application/octet-stream"

                if (mime_type_cmd.returncode == 0):
                    out = mime_type_cmd.stdout
                    _, mime_type = out.rsplit(":", 1)

                    if ("video" in mime_type):
                        ftype = "video"
                    elif ("audio" in mime_type):
                        ftype = "audio"
                    elif ("image" in mime_type):
                        ftype = "image"

                    elif ("application/pdf" in mime_type):
                        ftype = "pdf"
                    elif ("application/rtf" in mime_type):
                        ftype = "word"
                    elif ("text/csv" in mime_type):
                        ftype = "spreadsheet"
                    elif (("text" in mime_type) or ("shellscript" in mime_type)):
                        ftype = "text"
                    elif ("openxmlformats" in mime_type):
                        if ("wordprocessing" in mime_type):
                            ftype = "word"
                        elif ("spreadsheet" in mime_type):
                            ftype = "spreadsheet"
                        elif ("presentation" in mime_type):
                            ftype = "presentation"
                    elif ("opendocument" in mime_type):
                        if ("text" in mime_type):
                            ftype = "word"
                        elif ("spreadsheet" in mime_type):
                            ftype = "spreadsheet"
                        elif ("presentation" in mime_type):
                            ftype = "presentation"
                    elif ("msword" in mime_type):
                        ftype = "word"
                    elif ("ms-excel" in mime_type):
                        ftype = "spreadsheet"
                    elif ("ms-powerpoint" in mime_type):
                        ftype = "presentation"

                    else:
                        compressed = [
                            "application/zip",
                            "application/x-tar",
                            "application/x-compressed-tar",
                            "application/gzip",
                            "application/x-bzip2",
                            "application/x-xz",
                            "application/x-rar",
                            "application/vnd.rar",
                            "application/zstd",
                            "application/x-7z-compressed",
                            "application/x-lzip",
                            "application/x-lzma"
                        ]

                        if (any([t in mime_type for t in compressed])):
                            ftype = "zip"

                else:
                    CONFIG.warning(f"\t> {mime_type_cmd.stderr}")

            case _:
                ftype = "unk"
                mime_type = None

        try:
            return FileInfo(
                name=str(fname),
                size=int(size),
                type=ftype,
                mimetype = mime_type.strip(),
                real=True,
                owner=owner,
                shared=CONFIG.get_share_information(path),
                creation_time=int(creation_time),
                modification_time=modification_time
            )
        except Exception as e:
            CONFIG.warning(path)
            CONFIG.error((str(e)))
            raise e
    else:
        return None


def make_onlyoffice_configuration(path:Path, request:Request, user:Optional[UserProfile]= None, edit=False) -> Dict:
    p = str(path)

    file_info = get_file_info(p)

    stat = Stat(p, "%D:%i:%s:%Y",sudo=True).execute()

    if (stat.returncode == 0):
        raw_key = stat.stdout
    else:
        raw_key = p

    # CONFIG.warning(f"Onlyoffice key for {p}: {raw_key}")

    key = hashlib.md5(raw_key.encode()).hexdigest()

    # key = f"{p}:{file_info.modification_time}"

    filetype = "txt"
    documentType = file_info.type


    if (documentType == "word"):
        if ("openxmlformats" in file_info.mimetype):
            filetype = "docx"
        elif ("opendocument" in file_info.mimetype):
            filetype = "odt"
        elif ("ms" in file_info.mimetype):
            filetype = "doc"
        elif ("pdf" in file_info.mimetype):
            filetype = "pdf"
    elif (documentType == "presentation"):
        documentType = "slide"
        if ("openxmlformats" in file_info.mimetype):
            filetype = "pptx"
        elif ("opendocument" in file_info.mimetype):
            filetype = "odp"
        elif ("ms" in file_info.mimetype):
            filetype = "ppt"

    elif (documentType == "spreadsheet"):
        documentType = "cell"
        if ("openxmlformats" in file_info.mimetype):
            filetype = "xlsx"
        elif ("opendocument" in file_info.mimetype):
            filetype = "ods"
        elif ("ms" in file_info.mimetype):
            filetype = "xls"


    url_path = str(path.relative_to(CONFIG.mountpoint))

    if (url_path.startswith("/")):
        url_path = url_path[1:]


    url = request.url_for(
        "get_document",
        filename=url_path
    )

    callback = request.url_for(
        "onlyoffice_callback",
        filename=url_path
    )

    only_office_config = {
        "document": {
            "fileType": filetype,
            "key": key,
            "title": file_info.name,
            "url": str(url),
            "permissions": {
                "edit": edit,
                "download": True,
                "print": True,
                "comment": edit,
                "review": edit
            }
        },
        "documentType": documentType,
        "editorConfig": {
            "mode": "edit" if edit else "view",
            "callbackUrl": str(callback),
            "user": {
                "id": user.uid,
                "name": user.visible_name if user.visible_name is not None else user.username,
            } if user is not None else None
        }
    }

    token = jwt.encode(
        only_office_config,
        CONFIG.ONLYOFFICE_CONF['jwt_secret'],
        algorithm="HS256"
    )

    only_office_config["token"] = token

    return only_office_config


def is_allowed_onlyoffice_url(
    url: str,
    allowed_port: int = 8090
) -> bool:

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False

    if parsed.port != allowed_port:
        return False

    if parsed.hostname is None:
        return False

    allowed_ips = get_local_ips()

    try:
        ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        # hostname, e.g. "localhost"
        if parsed.hostname != "localhost":
            return False
        return True

    return str(ip) in allowed_ips

@fs.delete(
    "/mountpoint",
    responses={500: {"description": "Any internal errors"}},
    summary="Delete the directory of the mount point"
)
def rm_mountpoint(mountpoint:str,token:dict=Depends(verify_token)) -> None:
    check_permission(username:=token.get("username"), UserPermissions.POOL_CONF_DESTROY)

    if (CONFIG.is_pool_configured):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_CONFIG.name))

    if (CONFIG.is_mounted):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_MOUNTED.name))


    if (not mountpoint.startswith("/")) or (mountpoint.strip() == "/"):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_INVALID_MOUNTPOINT.name))

    parts = mountpoint.split("/")

    for i in range(len(parts),0,-1):
        path = "/".join(parts[:i])
        path = path.strip()

        if (path!="/") and (len(path)>0):
            process = subprocess.run(["sudo", "rmdir", path],capture_output=True)
            if (process.returncode != 0):
                raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_INVALID_MOUNTPOINT.name,params=[process.stderr.decode()]))

    CONFIG.warning(f"Mountpoint {mountpoint} has been removed by {username}.")





@fs.get("/browse",response_model=FSBrowse,summary="Get the list of files of the logged user.")
@fs.get("/browse/{path:path}",response_model=FSBrowse,summary="Get the list of files of the logged user.")
def ls_dir(path: Optional[str]=None, token:dict=Depends(verify_token)) -> FSBrowse:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username",None))

    if (not user):
        raise HTTPException(status_code=401)

    if (path is None):
        path = "."

    p = check_path_jail(user, path)

    ls = LS(str(p),sudo=True).execute()

    if (ls.returncode != 0):
        raise HTTPException(status_code=500)

    files:List[FileInfo] = []

    for f in ls.stdout.splitlines():
        current = p.joinpath(f)

        obj = get_file_info(str(current))

        if (obj is not None):
            files.append(obj)

    files.sort(key=lambda x: x.name)

    browsed_path = p.relative_to(user.home_dir)

    return FSBrowse(path=str(browsed_path),files=files)

@fs.get("/shared",response_model=List[SharedFileInfo],summary="Get the list of files shared with a specific user.")
def ls_shared(token:dict=Depends(verify_token)) -> List[SharedFileInfo]:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username",None))

    if (not user):
        raise HTTPException(status_code=401)

    files:List[SharedFileInfo] = []

    mountpoint = CONFIG.mountpoint

    for f,d in CONFIG.get_files_shared_with(user.username).items():
        obj = get_file_info(str(f))
        if (obj is not None):
            full_path = Path(f)


            files.append(
                SharedFileInfo(**obj.model_dump(),
                    can_edit = d.get("can_edit",False),
                    relative_path =  str(full_path.relative_to(mountpoint))
                )
            )

    files.sort(key=lambda x: x.name)

    CONFIG.flush_config()

    return files


@fs.get("/shared/{path:path}",response_model=FSBrowse,summary="Get the list of files in a shared directory shared with a specific user.")
def ls_shared_dir(path:str, token:dict=Depends(verify_token)) -> FSBrowse:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username",None))

    if (not user):
        raise HTTPException(status_code=401)

    files: List[SharedFileInfo] = []

    mountpoint = CONFIG.mountpoint
    requested_path:Path = Path(mountpoint) / path
    requested_path = requested_path.resolve()

    if (not requested_path.is_relative_to(Path(mountpoint).resolve())):
        raise HTTPException(status_code=401)

    shared_info:Optional[dict] = None

    for f, d in CONFIG.get_files_shared_with(user.username).items():
        share_path = Path(f).resolve()

        if (requested_path.is_relative_to(share_path)):
            shared_info = d
            break


    if (shared_info is None):
        raise HTTPException(status_code=401)

    ls = LS(str(requested_path)).execute()

    for f in ls.stdout.splitlines():
        current = requested_path.joinpath(f)

        obj = get_file_info(str(current))

        if (obj is not None):
            files.append(
                SharedFileInfo(**obj.model_dump(),
                               can_edit=shared_info.get("can_edit", False),
                               relative_path=str(current.relative_to(mountpoint))
                               )
            )

    return FSBrowse(path=path,files=files)




@fs.get("/checksum/{path:path}",response_model=str,summary="Get MD5 checksum of the specified file")
def checksum(path: Optional[str]=None, token:dict=Depends(verify_token)) -> str:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    if (path is None):
        path = "."

    try:
        p = check_path_jail(user, path)
    except HTTPException as e:
        p = check_shared_path(path, user.username)
        if (p is None):
            raise e


    obj = get_file_info(str(p))

    if ((obj is None) or (obj.type=="dir")):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_FS_NOT_FILE.name,params=[str(p)]))

    md5 = MD5Sum(str(p),sudo=True).execute()

    if (md5.returncode!=0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_UNKNOWN.name))

    output = md5.stdout

    regex = re.compile(r"([a-fA-F0-9]+)[ ]+(.+)")
    m = regex.match(output)

    if (m is None):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_UNKNOWN.name))

    return m[1]



@fs.post("/mkdir",summary="Create a new directory within the user space.")
def fs_mkdir(data:MkDirModel,token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    p = check_path_jail(user, data.path)

    new_dir = str(p.joinpath(data.new_dir))

    Mkdir(new_dir, sudo=True).execute() # i need to separate this due to probably race condition screwing up with Chown

    cmds = [
        Chown(user.username,user.username,new_dir,sudo=True),
        Chmod(new_dir,"700",sudo=True),
        SetfACL("backend", new_dir, mask="rwx", sudo=True),
        SetfACL("backend", new_dir, mask="rwx", recursive=True, sudo=True),
    ]

    trans = LocalCommandLineTransaction(*cmds)
    out = trans.run()

    if (not trans.success):
        errors = "\n ".join([x["stderr"] for x in out])
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_FS_MKDIR.name,params=[new_dir,errors]))

    CONFIG.info(f"New directory {p} created by {user.username}")

@fs.post("/share",summary="Enable a file or directory sharing with someone else (either another user or externally)", response_model=SharedFile)
def fs_share(share_conf:FileSharing,token:dict=Depends(verify_token)) -> SharedFile:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    path = check_path_jail(user, share_conf.path)

    expire_date = None

    if ((share_conf.expire is not None) and (share_conf.expire>0)):
        expire_date = datetime.now() + timedelta(days=share_conf.expire)
        expire_date = expire_date.timestamp()

    shared_with = None

    if (share_conf.sharing_permissions is not None):
        shared_with = {}

        for perms in share_conf.sharing_permissions:
            shared_with[perms.username] = {
                "can_edit":perms.can_edit
            }

    share_token = CONFIG.share_file(
        path = str(path),
        expire_date=expire_date,
        share_with=shared_with,
    )

    CONFIG.flush_config()
    CONFIG.trigger_event(Events.FILE_SHARED, {
        EventContext.TRIGGER_USER.value: user.username,
        EventContext.TOKEN : token
    })

    return SharedFile(token=share_token)

@fs.delete("/share/{path:path}",summary="Remove a file sharing")
def fs_share_delete(path:str,token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    p = check_path_jail(user, path)

    CONFIG.remove_share_file(str(p))

    CONFIG.flush_config()



@fs.post("/mv",summary="Rename or move a file/directory within the user space.")
def fs_mv(data:MvModel,token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    old = check_path_jail(user, data.old_path)
    new = check_path_jail(user, data.new_path,stat_last=False)

    out = Move(str(old),str(new),sudo=True).execute()

    if (out.returncode != 0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_FS_COPY.name,params=[old,out.stderr]))


    CONFIG.info(f"File moved {old} -> {new} by {user.username}")


@fs.post("/cp",summary="Copy a file/directory within the user space.")
def fs_cp(data:CpModel,token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    src = check_path_jail(user, data.src)
    dst = check_path_jail(user, data.dst,stat_last=False)

    file_info = get_file_info(str(src))
    recursive = file_info.type == "dir"

    path_root,ext = os.path.splitext(dst)

    idx=1

    unique = False

    while not unique:
        cmd = Stat(dst_full_path:=str(dst),sudo=True).execute()
        if (cmd.returncode == 0):
            dst = Path(f"{path_root}({idx}){ext}")
            idx+=1
        else:
            unique = True

    out = Copy(str(src),str(dst),recursive=recursive,sudo=True).execute()

    if (out.returncode != 0):
        raise HTTPException(status_code=400)


    flags = ['-R'] if recursive else []


    cmds = [
        Chown(user.username, user.username, dst_full_path,flags=flags, sudo=True),
        Chmod(dst_full_path, "700",flags=flags, sudo=True),
        SetfACL("backend", dst_full_path, mask="rwx", sudo=True),
    ]

    if (recursive):
        cmds.append(SetfACL("backend", dst_full_path, mask="rwx", recursive=True, sudo=True))

    trans = LocalCommandLineTransaction(*cmds)
    output = trans.run()

    if (not trans.success):
        errors = "\n ".join([x["stderr"] for x in output])
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_FS_COPY.name,params=[src,errors]))

    CONFIG.info(f"File {src} copied {dst} by {user.username}")

@fs.post("/upload",summary="Initiate an upload session via TUS protocol")
def fs_upload(request:Request, token:dict=Depends(verify_token)) -> Response:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    upload_length = request.headers.get("Upload-Length")
    metadata = request.headers.get("Upload-Metadata", "")

    if not upload_length:
        raise HTTPException(400, "Upload-Length required")

    def parse_metadata(header: str):
        metadata = {}

        if not header:
            return metadata

        pairs = header.split(",")

        for pair in pairs:
            try:
                key, value = pair.strip().split(" ", 1)
                decoded = base64.b64decode(value).decode("utf-8")
                metadata[key] = decoded
            except Exception as e:
                raise Exception(str(header))

        return metadata

    parsed_metadata = parse_metadata(metadata)
    upload_id = CONFIG.init_upload(int(upload_length),parsed_metadata, user)

    location = request.url_for("chunk_upload", upload_id=upload_id)


    CONFIG.info(f"Upload session {upload_id} initiated by {user.username}")

    return Response(
        status_code=201,
        headers={
            "Location": str(location),
            "Tus-Resumable": TUS_VERSION,
        },
    )

@fs.options("/upload")
def options_upload():
    return Response(
        status_code=204,
        headers={
            "Tus-Resumable": TUS_VERSION,
            "Tus-Version": "1.0.0",
            "Tus-Extension": "creation,expiration,termination",
        },
    )

@fs.head("/upload/{upload_id}", summary="Retrieve information regarding an upload session")
def head_upload(upload_id: str,token:dict=Depends(verify_token)) -> Response:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    meta = CONFIG.get_upload_session(upload_id)

    if (user.username != meta['user'].username):
        raise HTTPException(status_code=401)

    offset = 0

    if (meta is None):
        return Response(
            status_code=404,
            headers={
                "Tus-Resumable": TUS_VERSION,
                "Upload-Offset": str(offset),
            }
        )

    fname = meta.get("metadata", {}).get("name", upload_id)
    rel_path = meta.get("metadata", {}).get("path", ".")
    p = check_path_jail(user, rel_path)

    upload_full_path = p.joinpath(fname)

    ch_cmd = [
        Chown(os.getuid(),os.getgid(),path=str(upload_full_path)),
        Chmod(str(upload_full_path),"550"),
    ]

    tran = LocalCommandLineTransaction(*ch_cmd,privileged=True)

    obj = get_file_info(str(upload_full_path))


    if (obj is None):
        Touch(str(upload_full_path),sudo=True).execute()
        tran.run()
    else:
        tran.run()
        if (meta.get("metadata", {}).get("overwrite", False) ):
            Truncate(str(upload_full_path)).execute()
        else:
            offset = obj.size
            CONFIG.increment_upload_offset(upload_id, offset,reset=True)

    return Response(
        status_code=200,
        headers={
            "Upload-Offset": str(offset),
            "Upload-Length": str(meta.get("length",0)),
            "Tus-Resumable": TUS_VERSION,
        },
    )

@fs.patch("/upload/{upload_id}", summary="Upload a chunk of a file upload session")
async def chunk_upload(upload_id: str, request: Request, token:dict=Depends(verify_token)) -> Response:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    meta = CONFIG.get_upload_session(upload_id)
    fname = meta.get("metadata", {}).get("name", upload_id)

    rel_path = meta.get("metadata",{}).get("path",".")
    p = check_path_jail(user, rel_path)

    complete_file_path = str(p.joinpath(fname))

    upload_offset = int(request.headers.get("Upload-Offset",0))
    actual_offset = meta.get("offset", 0)

    expires = datetime.now(UTC) + timedelta(hours=24)
    formated_expire_date = format_datetime(expires, usegmt=True)

    try:

        if (actual_offset!=upload_offset):
            CONFIG.error(f"Upload session {upload_id} does not have the correct offset ({actual_offset}!={upload_offset})])")
            raise Exception()

        chunk = await request.body()
        actual_upload_length = len(chunk)

        subprocess.run(
            [
                "sudo",
                "dd",
                f"of={complete_file_path}",
                "bs=1",
                f"seek={upload_offset}",
                "conv=notrunc",
                "status=none",
            ],
            input=chunk,
            check=True,
        )

        # with (open(complete_file_path,"r+b")) as f:
        #     f.seek(upload_offset)
        #     f.write(chunk)

    except Exception as e:
        CONFIG.error(e)

        return Response(
            status_code=409,
            headers={
                "Upload-Offset": str(actual_offset),
                "Tus-Resumable": TUS_VERSION,
                "Upload-Expires": formated_expire_date,
            }
        )


    CONFIG.info(f"New chunk for {upload_id} of size {actual_upload_length} received from {user.username}")

    offset = CONFIG.increment_upload_offset(upload_id,actual_upload_length)

    if (CONFIG.is_upload_complete(upload_id)):
        cmds = [
            Chown(user.username, user.username, complete_file_path, sudo=True),
            Chmod(complete_file_path, "700", sudo=True),
            SetfACL("backend", complete_file_path,mask="rwx", sudo=True),
        ]

        LocalCommandLineTransaction(*cmds).run()
        CONFIG.info(f"Upload {upload_id} finished successfully: {complete_file_path}")
        CONFIG.delete_upload_session(upload_id)


    return Response(
        status_code=204,
        headers={
            "Upload-Offset": str(offset),
            "Tus-Resumable": TUS_VERSION,
            "Upload-Expires": formated_expire_date,
        })


@fs.delete("/upload/{upload_id}")
async def terminate_upload(upload_id: str, token:dict=Depends(verify_token)) -> Response:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    meta = CONFIG.get_upload_session(upload_id)

    if meta is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    rel_path = meta.get("metadata", {}).get("path", ".")
    fname = meta.get("metadata", {}).get("name", upload_id)

    p = check_path_jail(user, rel_path)

    RemoveFile(str(p.joinpath(fname))).execute()

    CONFIG.delete_upload_session(upload_id)

    CONFIG.warning(f"Upload {upload_id} terminated by {user.username}")

    return Response(
        status_code=204,
        headers={
            "Tus-Resumable": TUS_VERSION
        }
    )




@fs.get("/item/{filename:path}")
def download_file(filename: str, token:dict=Depends(verify_token)) -> StreamingResponse:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    try:
        p = check_path_jail(user, filename)
        stat = Stat(str(p),format="%F",sudo=True).execute()

        if ((stat.returncode != 0) or ("regular file" not in stat.stdout)):
            raise HTTPException(status_code=400)
    except HTTPException as e:
        p = check_shared_path(filename, user.username)
        if (p is None):
            raise e

    fname = p.name

    if (len(fname) == 0):
        raise HTTPException(status_code=500)

    file_info = get_file_info(str(p))

    CONFIG.info(f"File {filename} downloaded by {user.username}")

    return StreamingResponse(
        file_generator(str(p)),
        media_type=file_info.mimetype,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )

@fs.get("/onlyoffice/{filename:path}")
def onlyoffice_session(filename: str, request:Request, token:dict=Depends(verify_token)) -> Dict:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    edit=True

    try:
        p = check_path_jail(user, filename)
    except HTTPException:
        p,edit = shared_file_check_authorisation(filename, token)
        # CONFIG.warning(f" {user.username} can edit: {filename}: {edit}")

    stat = Stat(str(p),format="%F",sudo=True).execute()

    if (stat.returncode != 0) or ("regular file" not in stat.stdout):
        raise HTTPException(status_code=400)

    fname = p.name

    if (len(fname) == 0):
        raise HTTPException(status_code=500)

    return make_onlyoffice_configuration(p,request,user,edit)

@fs.delete("/item/{filename:path}",summary="Delete a file/directory within the user space.")
def fs_rm(filename: str, token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    p = check_path_jail(user, filename)

    stat = Stat(str(p), format="%F", sudo=True).execute()

    if (stat.returncode != 0):
        raise HTTPException(status_code=400)

    is_dir = "directory" in stat.stdout

    out = RemoveFile(p, is_dir=is_dir,sudo=True).execute()

    CONFIG.warning(f"File {filename} deleted by {user.username}")

    if (out.returncode != 0):
        raise HTTPException(status_code=500)

@fs.head("/preview/{filename:path}",summary="Generate a token for preview (this is to accommodate <video>)")
def get_preview_token(filename: str, token:dict=Depends(verify_token)) -> Response:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    try:
        p = check_path_jail(user, filename)
    except HTTPException as e:
        p = check_shared_path(filename, user.username)
        if (p is None):
            raise e

    path = str(p)

    file_info = get_file_info(path)

    if ((file_info is None) or (file_info.type == 'dir')):
        raise HTTPException(status_code=400)

    token = create_token(user.username,filename,60)

    return Response(
        status_code=200,
        headers={"X-Preview-Token": token},
    )

@fs_preview.get("/preview/{filename:path}", dependencies=[], summary="Generate a stream for previews. The token required here must be obtained by the HEAD method to the same endpoint.")
def preview_file(filename: str, request:Request, token:str) -> StreamingResponse:
    token_data = token_verification(token, filename)

    check_permission(token_data.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token_data.get("username", None))


    if (not user):
        raise HTTPException(status_code=401)

    try:
        p = check_path_jail(user, filename)
    except HTTPException as e:
        p = check_shared_path(filename, user.username)
        if (p is None):
            raise e


    path = str(p)

    file_info = get_file_info(path)
    headers = {}
    revoke_token = True
    partial_response = False
    response = None

    if (file_info is None):
        raise HTTPException(status_code=400)



    match (file_info.type):
        case "text"|"pdf":
            mimetype = "text/plain" if file_info.type != "pdf" else "application/pdf"
            generator = file_generator_dd(path)
        case "zip":
            mimetype = "text/plain"
            zip_content = ALS(path).execute()

            if (zip_content.returncode!=0):
                CONFIG.warning(f"Cannot LS this archive file: {file_info.type}")
                raise HTTPException(status_code=400)

            generator = zip_content.stdout

        case "image":
            mimetype = "image/png"

            result = subprocess.run(
                ["sudo", "cat", path],
                stdout=subprocess.PIPE,
                check=True
            )

            img = Image.open(BytesIO(result.stdout))
            img.thumbnail((500,500))

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            generator = buffer
            buffer.seek(0)
        case "video" | "audio":
            #revoke_token = False <- this may incur in a bug but let's keep it commented for a time being - not critical
            response = FileResponse(
                path,
                media_type=file_info.mimetype or "application/octet-stream",
                content_disposition_type="inline",
                headers={
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )
        case _:
            CONFIG.warning(f"Cannot preview this file type: {file_info.type}")
            raise HTTPException(status_code=400)



    if (revoke_token):
        CONFIG.revoke_token(token)


    CONFIG.info(f"File {filename} is being previewed by {user.username}")

    return StreamingResponse(
        generator,
        status_code=206 if partial_response else 200,
        media_type=mimetype,
        headers=headers,
    ) if response is None else response


@fs.post("/zip",summary="Compress the provided files in a compressed zip archive.")
def zip(data:ZipFile, token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    zip_basepath,zip_filename = os.path.split(data.zip_filename)

    p = check_path_jail(user, zip_basepath)

    files_to_compress = []

    for f in data.files:
        check_path_jail(user, f)

        try:
            files_to_compress.append( str(Path(f).relative_to(zip_basepath)) )
        except ValueError:
            raise HTTPException(status_code=500,)

    fullpath = str(p)

    match (data.format):
        case "zip":
            compression_algorithm = Zip(zip_filename,files_to_compress,cwd=fullpath,sudo=True)
        case "gz":
            compression_algorithm = TarArchive(".",zip_filename,TarArchive.TarAction.CREATE,TarArchive.TarCompression.GZIP,files_to_compress,cwd=fullpath,sudo=True)
        case "bz2":
            compression_algorithm = TarArchive(".", zip_filename, TarArchive.TarAction.CREATE,
                                               TarArchive.TarCompression.BZIP2, files_to_compress, cwd=fullpath,
                                               sudo=True)
        case "xz":
            compression_algorithm = TarArchive(".", zip_filename, TarArchive.TarAction.CREATE,
                                               TarArchive.TarCompression.XZ, files_to_compress, cwd=fullpath,
                                               sudo=True)
        case '7z':
            compression_algorithm = SevenZip(zip_filename,
                                             action=SevenZip.SevenZipAction.CREATE,
                                             files=files_to_compress,
                                             cwd=fullpath,sudo=True)

    cmds = [
            compression_algorithm,
            Chown(user.username, user.username, fullpath,sudo=True),
            Chmod(fullpath, "700",sudo=True),
            SetfACL("backend", fullpath,mask="rwx",sudo=True),
        ]

    trans = LocalCommandLineTransaction(*cmds)
    output = trans.run()

    if (not trans.success):
        errors = "\n ".join([x["stderr"] for x in output])
        errors += "\n ".join([x["stdout"] for x in output]) #zip sucks and puts errors in the stdout
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_FS_ZIP.name, params=[zip_filename, errors]))

@fs.post("/unzip/{filename:path}",summary="Decompress most of compressed archives (despite the name)")
def unzip(filename: str, token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    p = check_path_jail(user, filename)
    fullpath = str(p)
    basepath,fname = os.path.split(fullpath)

    file_info = get_file_info(fullpath)

    if ((file_info is None) or (file_info.type != 'zip')):
        raise HTTPException(status_code=400)

    if ("7z" in file_info.mimetype):
        uncompress_command = SevenZip(fullpath,SevenZip.SevenZipAction.EXTRACT,cwd=basepath,sudo=True)
    else:
        uncompress_command = Unpack(fullpath, cwd=basepath, sudo=True) # unpack doesn't like much 7z apparently

    cmds = [
            uncompress_command,
            Chown(user.username, user.username, basepath, flags=["-R"] ,sudo=True),
            Chmod(basepath, "700", flags=["-R"] ,sudo=True),
            SetfACL("backend", basepath,mask="rwx",recursive=True,sudo=True),
        ]

    trans = LocalCommandLineTransaction(*cmds)
    output = trans.run()

    if (not trans.success):
        errors = "\n ".join([x["stderr"] for x in output])
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_FS_UNZIP.name, params=[fname, errors]))



@fs.get("/quota",summary="Quota usage of the logged user.",response_model=Quota)
def fs_quota(token:dict=Depends(verify_token)) -> Quota:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    used = user.quota.used
    limit = user.quota.quota if user.quota.quota > 0 else CONFIG.get_pool_capacity.get('total')

    return Quota(used=used,quota=limit)


@onlyoffice.get("/file/{filename:path}",name="get_document")
def get_document(filename: str,token:dict=Depends(verify_onlyoffice)) -> Response:
    path = Path(CONFIG.mountpoint,filename).resolve()

    if (not path.is_relative_to(Path(CONFIG.mountpoint).resolve())):
        raise HTTPException(status_code=401)

    file_info = get_file_info(str(path))

    return StreamingResponse(
        file_generator_dd(str(path)),
        media_type=file_info.mimetype,
    )

@onlyoffice.post("/save/{filename:path}")
async def onlyoffice_callback(filename:str,request: Request) -> Dict:
    data = await request.json()

    token = data.get("token")
    if not token:
        raise HTTPException(401, "Missing ONLYOFFICE token")

    verify_onlyoffice_token(token)

    status = data.get("status")


    if status in (2,6):
        file_url = data["url"]

        if (not is_allowed_onlyoffice_url(file_url)):
            raise HTTPException(
                403,
                "Invalid OnlyOffice URL"
            )


        path = Path(CONFIG.mountpoint, filename).resolve()

        mountpoint = Path(CONFIG.mountpoint).resolve()

        if ((mountpoint not in path.parents) and (path != mountpoint)):
            raise HTTPException(403, "Invalid path")

        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream("GET", file_url) as r:
                r.raise_for_status()

                content_type = r.headers.get("content-type", "")

                if ("html" in content_type.lower()):
                    raise HTTPException(500, "Unexpected HTML response")

                proc = subprocess.Popen(
                    ["sudo", "tee", str(path)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE
                )

                if proc.stdin is None:
                    raise HTTPException(500, "tee stdin unavailable")

                async for chunk in r.aiter_bytes():
                    proc.stdin.write(chunk)

                proc.stdin.close()
                return_code = proc.wait()
                stderr = proc.stderr.read() if proc.stderr else b""

                if return_code != 0:
                    raise HTTPException(
                        500,
                        stderr.decode(errors="ignore")
                    )


    return {"error": 0}



@file_sharing.get("/browse",response_model=List[SharedFileInfo],summary="Get the list of files shared via the sharing token.")
@file_sharing.get("/browse/{rel_path:path}",response_model=List[SharedFileInfo],summary="Get the list of files shared via the sharing token.")
def ls_anon_shared(
        rel_path: Optional[str] = None,
        auth_token:Optional[dict] = Depends(verify_user_token_shared_files),
        share_token:dict=Depends(verify_shared_file_token)) -> List[SharedFileInfo]:

    authorised = False
    can_edit = False

    if (((share_with:=share_token.get("share_with",{})) is None) or (len(share_with)==0)):
        authorised = True
    else:
        if (auth_token is not None):
            user = CONFIG.get_user(auth_token.get("username", None))
            if ((user is not None) and (user.username in share_with.keys())):
                authorised = True
                can_edit = share_with[user.username].get("can_edit", False)


    if (not authorised):
        raise HTTPException(status_code=401)


    files: List[SharedFileInfo] = []

    mountpoint = Path(CONFIG.mountpoint)
    path: Optional[str] = share_token.get("path", None)



    if (path is not None):
        requested_path = Path(path).resolve()
        if (rel_path is not None):
            requested_path /= rel_path

        if (not requested_path.is_relative_to(Path(path).resolve())):
            raise HTTPException(status_code=403)

        obj = get_file_info(path)

        if (obj.type == "dir"):
            ls = LS(str(requested_path), sudo=True).execute()

            for p in ls.stdout.splitlines():
                full_path = (requested_path / p).resolve()
                obj = get_file_info(str(full_path))

                files.append(
                    SharedFileInfo(
                        **obj.model_dump(),
                        relative_path=str(full_path.relative_to(mountpoint)),
                        can_edit=can_edit
                    )
                )
                

        else:
            files.append(SharedFileInfo(**obj.model_dump(),
                                relative_path=str(requested_path.relative_to(mountpoint)),
                                can_edit=can_edit))

    return files

@file_sharing.get("/onlyoffice/{rel_path:path}")
def onlyoffice_anon_shared(
        request:Request,
        rel_path: str,
        auth_token:Optional[dict] = Depends(verify_user_token_shared_files),
        share_token:dict=Depends(verify_shared_file_token)) -> Optional[Dict]:

    authorised = False
    can_edit = False

    user = None

    if (((share_with := share_token.get("share_with", {})) is None) or (len(share_with) == 0)):
        authorised = True

    if (auth_token is not None):
        user = CONFIG.get_user(auth_token.get("username", None))
        if ((user is not None) and (user.username in share_with.keys())):
            authorised = True
            can_edit = share_with[user.username].get("can_edit", False)

    if (not authorised):
        raise HTTPException(status_code=401)


    path: Optional[str] = share_token.get("path", None)

    if (path is None):
        return None

    shared_path = Path(path).resolve()

    if (not shared_path.is_relative_to(CONFIG.mountpoint)):
        raise HTTPException(status_code=401)

    requested_path = Path(path).resolve()

    obj = get_file_info(requested_path)

    if (obj.type == "dir"):
        requested_path /= rel_path

        if ((not requested_path.is_relative_to(Path(path).resolve())) or (not requested_path.is_relative_to(Path(CONFIG.mountpoint).resolve()))):
            raise HTTPException(status_code=401)


    return make_onlyoffice_configuration(requested_path,request,user,can_edit)