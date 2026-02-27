from .responses import ErrorMessage
from abc import abstractmethod
from backend_server.utils.cmdl import ChPasswd, SystemCtlUnmask, SystemCtlEnable, SystemCtlStart, SystemCtlDisable, \
    Touch, Chmod, UserModAddGroup, GPasswdRemoveGroup
from backend_server.utils.cmdl import DockerInspect, DockerRemove, LocalCommandLineTransaction
from backend_server.utils.cmdl import SystemCtlIsActive, ApplyPatch,  GetEntShadow, UserModChangeShell, UserDel
from backend_server.utils.cmdl import SystemCtlMask, SystemCtlStop, ExportfsRA, SMBPasswd, DockerRun, DockerStop
from fastapi import HTTPException
from nms_shared.enums import UserPermissions
from nms_shared.msg import ErrorMessages
from nms_shared.utils import make_diff, read_lines_from_file
from pathlib import Path
from typing import Optional, Callable, List, Any, Self
import bcrypt
import configparser
import grp
import io
import os.path
import pwd
import re
import subprocess
import tempfile

class SystemService:
    def __init__(this,service_name:str, config_file:Optional[str]=None,**kwargs):
        this._service_name = service_name
        this._config_file = config_file
        this._change_hooks = {}
        this._pre_start_hooks = []
        this._permission_hook:Optional[UserPermissions] = None

    def add_change_hook(this,property:str,callback:Callable[[Self],None]) -> None:
        hooks = this._change_hooks.get(property,[])
        if (callback not in hooks):
            hooks.append(callback)

        this._change_hooks[property] = hooks

    def remove_change_hook(this,property:str,callback:Callable[[Self],None]) -> None:
        hooks = this._change_hooks.get(property, [])
        try:
            hooks.remove(callback)
        except ValueError:
            ...

        this._change_hooks[property] = hooks

    def add_pre_start_hook(this,callback:Callable[[Self],None]):
        if (callback not in this._pre_start_hooks):
            this._pre_start_hooks.append(callback)


    def remove_pre_start_hook(this,callback:Callable[[Self],None]):
        this._pre_start_hooks.append(callback)

    @property
    def service_names(this) -> str:
        return this._service_name

    @property
    def config_file(this) -> str:
        return this._config_file

    @property
    def properties(this) -> List[str]:
        return [k for k in vars(this.__class__).get("__annotations__",{}).keys()]

    @abstractmethod
    def get(this,property:str) -> Any:
        return getattr(this,f"get_{property}")()

    @abstractmethod
    def set(this, property:str, value:Any) -> None:
        getattr(this,f"set_{property}")(value)

        hooks = this._change_hooks.get(property,[])

        for callback in hooks:
            callback(this)

    @property
    def is_active(this) -> bool:
        names = this.service_names

        if (isinstance(names,str)):
            cmds = [SystemCtlIsActive(names)]
            n_services = 1
        else:
            cmds = [SystemCtlIsActive(n) for n in names]
            n_services = len(cmds)

        trans = LocalCommandLineTransaction(*cmds)

        results = trans.run()

        return sum([r.get("stdout","").strip() == "active" for r in results]) == n_services


    def start(this) -> None:
        hooks = this._pre_start_hooks

        for callback in hooks:
            callback(this)

        names = this.service_names
        cmds = []

        if (isinstance(names, str)):
            names = [names]


        for n in names:
            cmds.extend([
                SystemCtlUnmask(n),
                SystemCtlEnable(n),
                SystemCtlStart(n),
            ])

        trans = LocalCommandLineTransaction(*cmds)

        results = trans.run()

        if (not trans.success):
            raise Exception(f"The service(s) `{', '.join(names)}` could not be started: {[x.get('stderr', '') for x in results]}")

    def stop(this) -> None:
        names = this.service_names
        cmds = []

        if (isinstance(names, str)):
            names = [names]

        for n in names:
            cmds.extend([
                SystemCtlStop(n),
                SystemCtlDisable(n),
                SystemCtlMask(n),
            ])

        trans = LocalCommandLineTransaction(*cmds)

        results = trans.run()

        if (not trans.success):
            raise Exception(f"The service(s) `{', '.join(names)}` could not be stopped: {[x.get('stderr', '') for x in results]}")

    def permission_granted(this,username:str) -> None:
        ...

    def permission_revoked(this,username:str) -> None:
        ...

    def remove_user(this,username:str,**kwargs) -> None:
        ...

    @property
    def permission_hook(this) -> Optional[UserPermissions]:
        return this._permission_hook

class SSHService(SystemService):
    port:int

    def __init__(this,service_name,**kwargs):
        super().__init__(service_name,"/etc/ssh/sshd_config",**kwargs)
        this._permission_hook = UserPermissions.SERVICES_SSH_ACCESS

    def get_port(this) -> int:
        port = 22  # default

        with open(this.config_file, "r") as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                if "#" in line:
                    line = line.split("#", 1)[0].strip()

                parts = line.split()
                if len(parts) >= 2 and parts[0].lower() == "port":
                    try:
                        port = int(parts[1])
                    except ValueError:
                        pass  # ignore malformed port entries

        return port


    def set_port(this,new_port) -> None:
        orig_lines = read_lines_from_file(this.config_file)
        mod_lines = orig_lines.copy()
        found = False

        new_port_string = f"Port {new_port}\n"

        for i, line in enumerate(mod_lines):
            stripped = line.strip()
            if stripped.lower().startswith("port") or stripped.lower().startswith("#port"):
                mod_lines[i] = new_port_string
                found = True
                break

        if not found:
            if mod_lines and not mod_lines[-1].endswith("\n"):
                mod_lines[-1] = mod_lines[-1] + "\n"
            mod_lines.append(new_port_string)

        patch_text = make_diff(this.config_file, mod_lines)

        patch_fname = os.path.join(tempfile.gettempdir(),f"sshd_config.patch")
        Path(patch_fname).write_text(patch_text, encoding="utf-8", errors="surrogateescape")

        cmd = ApplyPatch(patch_fname,this.config_file,sudo=True)
        trans = LocalCommandLineTransaction(cmd)

        trans.run()
        os.remove(patch_fname)


    def set_password(this,username:str,new_password:str) -> None:
        shadow_cmd = GetEntShadow(username)

        trans = LocalCommandLineTransaction(shadow_cmd)
        output = trans.run()

        if (len(output)!=1):
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_USER_NOT_FOUND.name,params=[username]))

        stdout_getent = output[0].get("stdout","").split(":",2)
        uname = stdout_getent[0].strip()
        shadow_password = stdout_getent[1].strip()

        if (len(shadow_password) == 0):
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_USER_NOT_FOUND.name,params=[username]))

        if (uname != username):
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_USER_NOT_FOUND.name,params=[username]))

        chpasswd = ChPasswd(uname,new_password,shadow_password)

        output = chpasswd.execute()

        if (output.returncode != 0):
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_USER_PASSWD.name,params=[username]))

    def enable(this,port:int,**kwargs) -> None:
        if (port != this.get("port")):
            this.set("port", port)
        this.start()

    def disable(this,*args,**kwargs) -> None:
        this.stop()

    def permission_granted(this, username: str) -> None:
        UserModChangeShell(username,"/usr/bin/bash").execute()

    def permission_revoked(this, username: str) -> None:
        UserModChangeShell(username, "/usr/sbin/nologin").execute()

    def remove_user(this, username: str, **kwargs) -> None:
        UserDel(username,keep_home=kwargs.get("keep_home",False)).execute()




class FTPService(SystemService):
    USERLIST_FILE = "/etc/vsftpd.userlist"

    default_configuration={
        "anonymous_enable":"NO",
        "local_enable": "YES",
        "write_enable": "YES",
        "ftpd_banner": "Welcome to NMS FTP Service.",
        "chroot_local_user":"NO",
        "userlist_enable": "YES",
        "userlist_file": USERLIST_FILE,
        "userlist_deny": "NO",
        "utf8_filesystem":"YES",
        "chroot_list_enable":"NO",
    }
    def __init__(this,service_name, **kwargs):
        super().__init__(service_name,config_file="/etc/vsftpd.conf",**kwargs)
        this._permission_hook = UserPermissions.SERVICES_FTP_ACCESS

    def _patch_configuration(this) -> None:
        cfg = FTPService.default_configuration.copy()
        orig_lines = read_lines_from_file(this.config_file)
        mod_lines = orig_lines.copy()

        edited = False

        for i,original_line in enumerate(orig_lines):
            line = original_line.strip("#\n\r")
            tokens = line.split("=",2)
            if (len(tokens)>=2):
                key = tokens[0]

                if (key in cfg.keys()):
                    v = cfg[key]
                    del cfg[key]

                    if (original_line.strip().startswith("#") or (tokens[1]!=v)): # check if it's commented OR value is different
                        mod_lines[i] = f"{key}={v}\n"
                        edited=True

        if (len(cfg)>0):
            edited = True
            for k,v in cfg.items():
                mod_lines.append(f"{k}={v}\n")

        if (edited):
            patch_text = make_diff(this.config_file, mod_lines)

            patch_fname = os.path.join(tempfile.gettempdir(), f"vsftpd.patch")
            Path(patch_fname).write_text(patch_text, encoding="utf-8", errors="surrogateescape")

            cmd = ApplyPatch(patch_fname, this.config_file, sudo=True)
            trans = LocalCommandLineTransaction(cmd)

            trans.run()
            os.remove(patch_fname)

    def enable(this,*args,**kwargs) -> None:
        this._patch_configuration()
        this.start()

    def disable(this,*args,**kwargs) -> None:
        this.stop()

    def _touch_userlist_file(this) -> None:
        if (not os.path.exists(FTPService.USERLIST_FILE)):
            #chmod relies on the file existance to make a revert command.
            #if the file doesn't exist, it raises an exception
            #breaking these two calls will avoid that problem
            Touch(FTPService.USERLIST_FILE, sudo=True).execute()
            Chmod(FTPService.USERLIST_FILE, "600", sudo=True).execute()




    def permission_granted(this, username: str) -> None:
        this._touch_userlist_file()
        result = subprocess.run(
            ["sudo", "grep", "-qxF", username, FTPService.USERLIST_FILE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if result.returncode == 0:
            return  # already present

        # Append via sudo tee
        subprocess.run(
            ["sudo", "tee", "-a", FTPService.USERLIST_FILE],
            input=username + "\n",
            text=True,
            stdout=subprocess.DEVNULL,
            check=True
        )

    def permission_revoked(this, username: str) -> None:
        this._touch_userlist_file()
        subprocess.run(
            ["sudo", "sed", "-i", f"/^{username}$/d", FTPService.USERLIST_FILE],
            check=True
        )

    def remove_user(this, username: str, **kwargs) -> None:
        this.permission_revoked(username)


class NFSService(SystemService):
    ip:str
    default_options = ['rw','sync','no_subtree_check','all_squash']

    def __init__(this,service_name:str,mountpoint:Optional[str]=None,**kwargs):
        super().__init__(service_name,"/etc/exports",**kwargs)
        this._mountpoint = mountpoint
        this._permission_hook = UserPermissions.SERVICES_NFS_ACCESS

    @property
    def mountpoint(this) -> Optional[str]:
        return this._mountpoint

    def get_ip(this) -> Optional[str]:
        exports = read_lines_from_file(this.config_file)

        hostname = None

        for l in exports:
            if (not l.startswith("#")):
                if (this.mountpoint) and (this.mountpoint in l):
                    parts = [p.strip() for p in l.split()]
                    hosts = parts[1:]

                    for h in hosts:
                        m = re.match(r'^([^()]+)\(', h)
                        if m:
                            hostname = m.group(1).strip()
                            break

        return hostname

    def set_ip(this,hostname) -> None:
        if (this.mountpoint is None):
            raise Exception("You cannot activate this service if you don't set up a new disk array")

        exports = read_lines_from_file(this.config_file)
        new_exports = exports.copy()

        options = NFSService.default_options.copy()
        options.extend([
            f"anonuid={this.uid}",
            f"anongid={this.gid}"
        ])

        new_line = f"{this.mountpoint}\t{hostname}({','.join(options)})\n"

        for i,l in enumerate(exports):
            if (not l.startswith("#")):
                if (this.mountpoint in l):
                    new_exports[i] = new_line
                    break
        else:
            new_exports.append(new_line)

        patch_text = make_diff(this.config_file, new_exports)

        patch_fname = os.path.join(tempfile.gettempdir(), f"exports.patch")
        Path(patch_fname).write_text(patch_text, encoding="utf-8", errors="surrogateescape")

        cmd = ApplyPatch(patch_fname, this.config_file, sudo=True)
        trans = LocalCommandLineTransaction(cmd)

        trans.run()
        os.remove(patch_fname)

    def enable(this,ip,**kwargs) -> None:
        this.set("ip",ip)
        this.start()

    def start(this) -> None:
        trans = LocalCommandLineTransaction(ExportfsRA())

        trans.run()
        super().start()

    def disable(this,*args,**kwargs) -> None:
        this.stop()

    def update(this,ip,**kwargs) -> None:
        this.disable()
        this.enable(ip,**kwargs)




class SMBService(SystemService):
    username:str
    SECTION = "NMS"

    def __init__(this,mountpoint:Optional[str],service_name:str,**kwargs):
        super().__init__(service_name,config_file="/etc/samba/smb.conf")
        # this._username = username
        this._mountpoint = mountpoint
        this._permission_hook = UserPermissions.SERVICES_SMB_ACCESS

    @property
    def mountpoint(this) -> Optional[str]:
        return this._mountpoint

    def _patch_configuration(this) -> None:
        if (this.mountpoint is None):
            raise Exception("You cannot activate this service if you don't set up a new disk array")

        config = configparser.ConfigParser()
        config.read(this.config_file)

        config[SMBService.SECTION] = {
            'path': this.mountpoint,
        }

        new_output = io.StringIO()
        config.write(new_output)

        modified_file = new_output.getvalue()
        new_output.close()

        modified_lines = modified_file.splitlines(keepends=True)

        patch_text = make_diff(this.config_file, modified_lines)

        patch_fname = os.path.join(tempfile.gettempdir(), f"smb.conf.patch")
        Path(patch_fname).write_text(patch_text, encoding="utf-8", errors="surrogateescape")

        cmd = ApplyPatch(patch_fname, this.config_file, sudo=True)
        trans = LocalCommandLineTransaction(cmd)

        trans.run()
        os.remove(patch_fname)

    def set_password(this,username,password) -> None:
        cmd = SMBPasswd(username=username,password=password,flag=SMBPasswd.Flags.ADD)
        trans = LocalCommandLineTransaction(cmd)
        trans.run()

    def enable_user(this,username) -> None:
        cmd = SMBPasswd(username=username, flag=SMBPasswd.Flags.ENABLE)
        trans = LocalCommandLineTransaction(cmd)
        trans.run()

    def disable_user(this,username) -> None:
        cmd = SMBPasswd(username=username, flag=SMBPasswd.Flags.ENABLE)
        trans = LocalCommandLineTransaction(cmd)
        trans.run()

    def delete_user(this,username) -> None:
        cmd = SMBPasswd(username=username, flag=SMBPasswd.Flags.DELETE)
        trans = LocalCommandLineTransaction(cmd)
        trans.run()



    def enable(this,**kwargs) -> None:
        this._patch_configuration()

        # if (password is not None):
        #     this._add_user(username,password)


        this.start()

    def disable(this,**kwargs) -> None:
        # this._delete_user(username)
        this.stop()

    def permission_granted(this, username: str) -> None:
        UserModAddGroup(username,"sambashare").execute()

    def permission_revoked(this, username: str) -> None:
        GPasswdRemoveGroup(username,"sambashare").execute()

    def remove_user(this, username: str, **kwargs) -> None:
        this.permission_revoked(username)


class WEBService(SystemService):
    port:int
    username:str
    authentication:bool

    CONTAINER_NAME = "ifm:latest"
    ENV = {
        "IFM_DOWNLOAD": "1",
        "IFM_EXTRACT": "1",
        "IFM_UPLOAD": "1",
        "IFM_REMOTEUPLOAD": "0",
        "IFM_ZIPNLOAD": "1",
        "IFM_SHOWLASTMODIFIED":"1",
        "IFM_SHOWOWNER":"0",
        "IFM_SHOWGROUP": "0",
        "IFM_SHOWPERMISSIONS": "0",
        "IFM_AJAXREQUEST": "0"
    }

    def __init__(this,service_name,mountpoint,port,username=None,group=None,authentication=None,credential=None,*args,**kwargs):
        this._mountpoint = mountpoint
        this._port = port
        this._username = username
        this._group = group
        this._authentication = authentication
        this._credential = credential
        super().__init__(service_name)


    def get_port(this):
        return this._port

    def set_port(this,value):
        this._port = value

    def set_credential(this,value):
        this._credential = value

    def get_credential(this):
        return this._credential

    def get_username(this):
        return this._credential.split(":")[0]

    def set_authentication(this,value):
        this._authentication = value

    def get_authentication(this):
        return this._authentication

    def start(this):

        docker_remove = DockerRemove(container_name=this.service_names)

        trans = LocalCommandLineTransaction(docker_remove)
        trans.run()

        volumes = {
            this._mountpoint:"/var/www",
        }

        port = [(this.get_port(),80)]

        user_info = pwd.getpwnam(this._username)
        group_info = grp.getgrnam(this._group)

        uid = user_info.pw_uid
        gid = group_info.gr_gid

        env = WEBService.ENV.copy()
        env['IFM_DOCKER_UID'] = uid
        env['IFM_DOCKER_GID'] = gid

        env['IFM_AUTH'] = "1" if this._authentication else "0"

        if (this._authentication):
            env['IFM_AUTH_SOURCE'] = f"inline;{this._credential}"

        docker_run = DockerRun(
            container_name=WEBService.CONTAINER_NAME,
            image_name = this.service_names,
            port_forwarding=port,
            envvars=env,
            mount = volumes,
            remove=False,
            restart="unless-stopped"
        )

        trans = LocalCommandLineTransaction(docker_run)

        trans.run()

    def stop(this):

        cmds = [
            DockerStop(container_name=this.service_names),
            DockerRemove(container_name=this.service_names)
        ]

        trans = LocalCommandLineTransaction(*cmds)

        trans.run()

    def enable(this,port,**kwargs):
        this.set("port",int(port))
        this._update_credential(**kwargs)
        this.start()

    def disable(this,**kwargs):
        this.stop()
    #
    # def update(this,**kwargs):
    #     this._update_credential(**kwargs)

    def _update_credential(this,**kwargs):
        username = kwargs.get("username")
        password = kwargs.get("password")
        authentication = kwargs.get("authentication",False)

        curr_username,curr_password = this.get("credential").split(":")

        changed = False

        if (username is not None):
            curr_username = username
            changed = True

        if (password is not None) and (len(password)>0):
            hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12))
            curr_password = hashed_password.decode("utf-8")
            changed = True

        if (changed):
            credential = f"{curr_username}:{curr_password}"
            this.set("credential",credential)

        this.set("authentication",True if authentication else False)



    @property
    def is_active(this):
        docker_inspect = DockerInspect(
            container_name=this.service_names,
            flags=['-f','{{.State.Status}}']
        )

        trans = LocalCommandLineTransaction(docker_inspect)

        output = trans.run()

        if (trans.success):
            return True if output[0].get("stdout","").strip() == "running" else False
        else:
            return False
