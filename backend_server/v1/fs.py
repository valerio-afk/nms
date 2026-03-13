from backend_server.utils.cmdl import Chown, Chmod, LocalCommandLineTransaction, LS, Stat, MimeType, Mkdir, Move, \
    RemoveFile
from backend_server.utils.config import CONFIG
from backend_server.utils.responses import ErrorMessage, UserProfile, FileInfo, FSBrowse, MkDirModel, MvModel, Quota
from backend_server.v1.auth import verify_token_factory, check_permission
from fastapi import HTTPException, APIRouter, Depends, UploadFile, Form
from fastapi.responses import StreamingResponse
from nms_shared import ErrorMessages
from nms_shared.enums import UserPermissions
from pathlib import Path
from typing import Optional, List, Generator
import grp
import os
import pwd
import shutil
import subprocess

verify_token = verify_token_factory()

fs = APIRouter(
    prefix='/fs',
    tags=['fs'],
    dependencies=[Depends(verify_token)]
)

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

@fs.post(
    "/rm-mountpoint",
    responses={500: {"description": "Any internal errors"}},
    summary="Delete the directory of the mount point"
)
def rm_mountpoint(mountpoint:str,token:dict=Depends(verify_token)) -> None:
    check_permission(token.get("username"), UserPermissions.POOL_CONF_DESTROY)

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
        CONFIG.error(f"\t\t{path}")

        if (path!="/") and (len(path)>0):
            process = subprocess.run(["sudo", "rmdir", path],capture_output=True)
            if (process.returncode != 0):
                raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_INVALID_MOUNTPOINT.name,params=[process.stderr.decode()]))


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

@fs.post("/upload",summary="Upload a file/directory within the user space.")
def fs_upload(file:UploadFile,
              directory:str=Form(...),
              upload_id: str = Form(...),
              chunk_index: int = Form(...),
              total_chunks: int = Form(...),
              token:dict=Depends(verify_token)) -> dict:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    if (not user):
        raise HTTPException(status_code=401)

    p = check_path_jail(user, directory)

    chunk_filename = f".chunk_{upload_id}_{chunk_index}"
    chunk_tmp_path = os.path.join("/tmp",chunk_filename)
    chunk_file_path = str(p.joinpath(chunk_filename))

    with (open(chunk_tmp_path,"wb")) as h:
        shutil.copyfileobj(file.file, h)

    mv_out = Move(chunk_tmp_path,chunk_file_path,sudo=True).execute()

    if (mv_out.returncode != 0):
        raise HTTPException(status_code=500)


    ls_out = LS(f".chunk_{upload_id}_*",sudo=True).execute()

    if (ls_out.returncode != 0):
        raise HTTPException(status_code=500)

    current_count = len(ls_out.stdout.splitlines())

    if (current_count == total_chunks):
        complete_file_path = str(p.joinpath(file.filename))

        filenames = [f".chunk_{upload_id}_{i}" for i in range(1,total_chunks+1)]

        for f in filenames:
            tee_cmd = ['sudo','tee',complete_file_path]
            with subprocess.Popen(["cat", f], stdout=subprocess.PIPE) as proc:
                subprocess.run(tee_cmd,stdin=proc.stdout)
                proc.wait()

        for f in filenames:
            RemoveFile(f,sudo=True).execute()

        cmds = [
            Chown(user.username, user.username, complete_file_path, sudo=True),
            Chmod(complete_file_path, "700", sudo=True),
        ]

        LocalCommandLineTransaction(*cmds).run()

        return {
            "status": "complete",
            "filename": file.filename,
        }

    return {
        "status": "chuck received",
        "chunk_index": chunk_index,
    }

@fs.get("/download/{filename:path}")
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


    return StreamingResponse(
        _file_generator(filename),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )

@fs.get("/delete/{filename:path}",summary="Delete a file/directory within the user space.")
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

    if (out.returncode != 0):
        raise HTTPException(status_code=500)

@fs.get("/quota",summary="Quota usage of the logged user.",response_model=Quota)
def fs_quota(token:dict=Depends(verify_token)) -> Quota:
    check_permission(token.get("username"), UserPermissions.SERVICES_WEB_ACCESS)
    user = CONFIG.get_user(token.get("username", None))

    used = user.quota.used
    limit = user.quota.quota if user.quota.quota > 0 else CONFIG.get_pool_capacity.get('total')

    return Quota(used=used,quota=limit)