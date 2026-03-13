from backend_server.utils.cmdl import Chown, Chmod, LocalCommandLineTransaction, LS, Stat, MimeType, Mkdir, Move, \
    RemoveFile
from backend_server.utils.config import CONFIG
from backend_server.utils.responses import ErrorMessage, UserProfile, FileInfo, FSBrowse, MkDirModel, MvModel, Quota
from backend_server.v1.auth import verify_token_factory, check_permission
from datetime import datetime,timedelta, UTC
from email.utils import format_datetime
from fastapi import HTTPException, APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from nms_shared import ErrorMessages
from nms_shared.enums import UserPermissions
from pathlib import Path
from typing import Optional, List, Generator
import base64
import grp
import pwd
import os
import re
import subprocess
import uuid

verify_token = verify_token_factory()

fs = APIRouter(
    prefix='/fs',
    tags=['fs'],
    dependencies=[Depends(verify_token)]
)

TUS_VERSION = "1.0.0"

def get_upload_chunks(path:Path, upload_id:str)->List[str]:
    ls_cmd = LS(str(path)).execute()

    r = re.compile(r"^."+ upload_id +r"_([a-zA-Z0-9\-]{4,12}){4}\.nms\.chunk$")

    return [f for f in ls_cmd.stdout.splitlines() if r.match(f) is not None]

def delete_chunks(p:Path, upload_id:str)->None:
    chunks = get_upload_chunks(p, upload_id)

    for f in chunks:
        RemoveFile(f, sudo=True).execute()


def check_path_jail(user:UserProfile,path:str,stat_last:bool=True) -> Path:
    home = Path(user.home_dir)
    requested_path = home.joinpath(path).resolve()

    if (not requested_path.is_relative_to(home)):
        HTTPException(status_code=401)

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
            target = real_path.strip("'")
            if not target.is_relative_to(home):
                raise HTTPException(status_code=401)

    return requested_path




def change_permissions(path:str,group:str="users") -> None:
    if (not CONFIG.is_mounted):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_UNMOUNTED.name))


    # subprocess.run(["sudo","chown", f":{group}", "-R", mountpoint])
    # subprocess.run(["sudo","chmod", "770", "-R", mountpoint])

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
        HTTPException(status_code=500)

    files:List[FileInfo] = []

    for f in ls.stdout.splitlines():
        current = p.joinpath(f)
        stat = Stat(str(current),"%n\n%s\n%F\n%W",sudo=True).execute()

        if (stat.returncode == 0):
            fullpath,size,ftype,creation_time = (
                stat.stdout.splitlines())

            fname = Path(fullpath).relative_to(p)

            match(ftype):
                case "directory":
                    ftype = "dir"
                case "regular file":
                    mime_type = MimeType(str(current),sudo=True).execute()
                    ftype = "bin"

                    if (mime_type.returncode == 0):
                        out = mime_type.stdout
                        _,mime = out.rsplit(":",1)
                        if ("video" in mime):
                            ftype="video"
                        elif ("audio" in mime):
                            ftype="audio"
                        elif ("image" in mime):
                            ftype="image"
                        elif ("application/pdf" in mime):
                            ftype="pdf"
                        elif ("text" in mime):
                            ftype="text"
                        else:
                            compressed = [
                                "applcation/zip",
                                "application/x-tar",
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

                            if (any([t in mime for t in compressed])):
                                ftype = "zip"

                case _:
                    ftype = "unk"

            obj = FileInfo(
                name=str(fname),
                size=int(size),
                type=ftype,
                real = True,
                creation_time=int(creation_time)
            )
        else:
            obj = FileInfo(
                name=f,
                size=0,
                type="unk",
                real=False,
                creation_time=0
            )

        files.append(obj)

    files.sort(key=lambda x: x.name)

    browsed_path = p.relative_to(user.home_dir)

    return FSBrowse(path=str(browsed_path),files=files)

@fs.post("/mkdir",summary="Create a new directory within the user space.")
def fs_mkdir(data:MkDirModel,token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    p = check_path_jail(user, data.path)

    new_dir = str(p.joinpath(data.new_dir))

    cmds = [
        Mkdir(new_dir,sudo=True),
        Chown(user.username,user.username,new_dir,sudo=True),
        Chmod(new_dir,"700",sudo=True),
    ]

    trans = LocalCommandLineTransaction(*cmds)

    out = trans.run()

    if (not trans.success):
        raise HTTPException(status_code=400)

    CONFIG.info(f"New directory {p} created by {user.username}")


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
        raise HTTPException(status_code=400)

    CONFIG.info(f"File moved {old} -> {new} by {user.username}")


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
            key, value = pair.strip().split(" ", 1)
            decoded = base64.b64decode(value).decode("utf-8")
            metadata[key] = decoded

        return metadata

    upload_id = CONFIG.initiate_upload_session(int(upload_length),parse_metadata(metadata))

    location = request.url_for("chunk_upload", upload_id=upload_id)

    CONFIG.info(f"Upload session {upload_id} initiated by {user.username}")

    return Response(
        status_code=201,
        headers={
            "Location": location,
            "Tus-Resumable": TUS_VERSION,
        },
    )

@fs.options("/uploads")
def options_upload():
    return Response(
        status_code=204,
        headers={
            "Tus-Resumable": TUS_VERSION,
            "Tus-Version": "1.0.0",
            "Tus-Extension": "creation,expiration,termination",
        },
    )

@fs.head("/uploads/{upload_id}", summary="Retrieve information regarding an upload session")
def head_upload(upload_id: str,token:dict=Depends(verify_token)) -> Response:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    meta = CONFIG.get_upload_session(upload_id)

    return Response(
        status_code=200,
        headers={
            "Upload-Offset": str(meta.get("offset",0)),
            "Upload-Length": str(meta.get("length",0)),
            "Tus-Resumable": TUS_VERSION,
        },
    )

@fs.patch("/uploads/{upload_id}", summary="Upload a chunk of a file upload session")
async def chunk_upload(upload_id: str, request: Request, token:dict=Depends(verify_token)) -> Response:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    meta = CONFIG.get_upload_session(upload_id)
    rel_path = meta.get("metadata",{}).get("path",".")

    p = check_path_jail(user, rel_path)
    id = uuid.uuid4()

    chunk_fname = f".{upload_id}_{id}.nms.chunk"
    chunk_tmp_path = os.path.join("/tmp", chunk_fname)
    chunk_file_path = os.path.join(p, chunk_fname)

    chunk = await request.body()

    with (open(chunk_tmp_path,"wb")) as f:
        f.write(chunk)

    mv_out = Move(chunk_tmp_path, chunk_file_path, sudo=True).execute()

    expires = datetime.now(UTC) + timedelta(hours=24)
    formated_expire_date = format_datetime(expires, usegmt=True)

    CONFIG.info(f"New chunk for {upload_id} of size {len(chunk)} received from {user.username}")


    if (mv_out.returncode != 0):
        return Response(
            status_code=204,
            headers={
                "Upload-Offset": "0",
                "Tus-Resumable": TUS_VERSION,
                "Upload-Expires": formated_expire_date,
            }
        )

    offset = CONFIG.increment_upload_offset(upload_id,len(chunk))

    if (CONFIG.is_upload_complete(upload_id)):
        fname = meta.get("metadata",{}).get("filename",upload_id)

        complete_file_path = str(p.joinpath(fname))

        chunks  = get_upload_chunks(p,upload_id)

        for f in chunks:
            tee_cmd = ['sudo','tee',complete_file_path]
            with subprocess.Popen(["cat", p.joinpath(f)], stdout=subprocess.PIPE) as proc:
                subprocess.run(tee_cmd,stdin=proc.stdout)
                proc.wait()

        delete_chunks(p,upload_id)

        cmds = [
            Chown(user.username, user.username, complete_file_path, sudo=True),
            Chmod(complete_file_path, "700", sudo=True),
        ]

        LocalCommandLineTransaction(*cmds).run()
        CONFIG.info(f"Upload {upload_id} finished successfully: {complete_file_path}")

    return Response(
        status_code=204,
        headers={
            "Upload-Offset": str(offset),
            "Tus-Resumable": TUS_VERSION,
            "Upload-Expires": formated_expire_date,
        })


@fs.delete("/uploads/{upload_id}")
async def terminate_upload(upload_id: str, token:dict=Depends(verify_token)) -> Response:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    meta = CONFIG.get_upload_session(upload_id)

    if meta is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    rel_path = meta.get("metadata", {}).get("path", ".")

    p = check_path_jail(user, rel_path)

    delete_chunks(p,upload_id)

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

    p = check_path_jail(user, filename)

    stat = Stat(str(p),format="%F",sudo=True).execute()

    if (stat.returncode != 0) or ("regular file" not in stat.stdout):
        raise HTTPException(status_code=400)

    fname = p.name

    if (len(fname) == 0):
        raise HTTPException(status_code=500)

    def _file_generator(path:str,chunk_size=1024**2) -> Generator[bytes, None, None]:
        proc = subprocess.Popen(
            ["cat", path],
            stdout=subprocess.PIPE
        )

        while chuck:= proc.stdout.read(chunk_size):
            yield chuck

    CONFIG.info(f"File {filename} downloaded by {user.username}")

    return StreamingResponse(
        _file_generator(filename),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )

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

@fs.get("/quota",summary="Quota usage of the logged user.",response_model=Quota)
def fs_quota(token:dict=Depends(verify_token)) -> Quota:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    used = user.quota.used
    limit = user.quota.quota if user.quota.quota > 0 else CONFIG.get_pool_capacity.get('total')

    return Quota(used=used,quota=limit)