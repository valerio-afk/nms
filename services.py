import os.path
import tempfile
from abc import abstractmethod

from cmdl import RemoteCommandLineTransaction, SystemCtlIsActive, ApplyPatch, UserModChangeUsername, GetEntShadow, \
    ChPasswd, SystemCtlUnmask, SystemCtlEnable, SystemCtlStart, SystemCtlDisable, SystemCtlMask, SystemCtlStop, \
    SystemCtlRestart
from constants import SOCK_PATH
from nms_utils import make_diff, read_lines_from_file
from pathlib import Path
import socket

class SystemService:
    def __init__(this,service_name, config_file=None):
        this._service_name = service_name
        this._config_file = config_file
        this._change_hooks = {}
        this._pre_start_hooks = []

    def add_change_hook(this,property,callback):
        hooks = this._change_hooks.get(property,[])
        if (callback not in hooks):
            hooks.append(callback)

        this._change_hooks[property] = hooks

    def remove_change_hook(this,property,callback):
        hooks = this._change_hooks.get(property, [])
        try:
            hooks.remove(callback)
        except ValueError:
            ...

        this._change_hooks[property] = hooks

    def add_pre_start_hook(this,callback):
        if (callback not in this._pre_start_hooks):
            this._pre_start_hooks.append(callback)


    def remove_pre_start_hook(this,callback):
        this._pre_start_hooks.append(callback)

    @property
    def name(this):
        return this._service_name

    @property
    def config_file(this):
        return this._config_file

    @property
    def properties(this):
        return [k for k in vars(this.__class__).get("__annotations__",{}).keys()]

    @abstractmethod
    def get(this,property):
        return getattr(this,f"get_{property}")()

    @abstractmethod
    def set(this, property, value):
        getattr(this,f"set_{property}")(value)

        hooks = this._change_hooks.get(property,[])

        for callback in hooks:
            callback(this)

    @property
    def is_active(this):
        cmd = SystemCtlIsActive(this.name)
        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            cmd
        )

        results = trans.run()

        if (len(results) == 1):
            output = results[0]['stdout'].strip()
            return output == "active"
        else:
            return False

    def start(this):
        hooks = this._pre_start_hooks

        for callback in hooks:
            callback(this)


        cmds = [
            SystemCtlUnmask(this.name),
            SystemCtlEnable(this.name),
            SystemCtlStart(this.name),
        ]

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            *cmds
        )

        results = trans.run()

        if (not trans.success):
            raise Exception(f"The service `{this.name}` could not be started: {[x.get('stderr','') for x in results]}")

    def stop(this):
        cmds = [
            SystemCtlStop(this.name),
            SystemCtlDisable(this.name),
            SystemCtlMask(this.name),
        ]

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            *cmds
        )

        results = trans.run()

        if (not trans.success):
            raise Exception(f"The service `{this.name}` could not be started: {[x.get('stderr', '') for x in results]}")

class SSHService(SystemService):
    port:int
    username:str
    password:str

    def __init__(this,service_name,sys_user):
        super().__init__(service_name,"/etc/ssh/sshd_config")
        this._username = sys_user

    def get_port(this):
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

    def get_username(this):
        return this._username

    def set_port(this,new_port):
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
        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            cmd
        )

        trans.run()
        os.remove(patch_fname)

    def set_username(this,value):
        cmd = UserModChangeUsername(this.get("username"),value)

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            cmd
        )
        output = trans.run()

        if (len(output) == 1):
            if (not trans.success):
                raise Exception(f"Unable to change username: {output[0]['stderr']}")
            else:
                this._username = value

    def set_password(this,value):
        shadow_cmd = GetEntShadow(this.get("username"))

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            shadow_cmd
        )
        output = trans.run()

        if (len(output)!=1):
            raise Exception("Unable to retrieve the current password")

        stdout_getent = output[0].get("stdout","").split(":",2)
        uname = stdout_getent[0].strip()
        shadow_password = stdout_getent[1].strip()

        if (len(shadow_password) == 0):
            raise Exception("Unable to retrieve the current password")

        if (uname != this.get("username")):
            raise Exception("Usernames don't match")

        chpasswd = ChPasswd(uname,value,shadow_password)

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            chpasswd
        )
        output = trans.run()

        if ((len(output)!=1) or (output[0].get("returncode",-1) != 0)):
            raise Exception(f"Unable to change password for `{uname}`")

    def _update_data(this,port,username,password):
        if (port != this.get("port")):
            this.set("port",port)
        if (username != this.get("username")):
            this.set("username",username)
        if (len(password)!=0):
            this.set("password",password)

    def enable(this,port,username,password,**kwargs):
        this._update_data(port,username,password)
        this.start()

    def disable(this,*args,**kwargs):
        this.stop()

    def update(this, port, username, password, **kwargs):
        this._update_data(port, username, password)

        cmd = SystemCtlRestart(this.name)

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            cmd
        )
        output = trans.run()

        if (not trans.success):
            raise Exception(f"{this.name} could not be restarted")



class FTPService(SystemService):
    default_configuration={
        "anonymous_enable":"NO",
        "local_enable": "YES",
        "write_enable": "YES",
        "ftpd_banner": "Welcome to NMS FTP Service.",
        "chroot_local_user":"NO",
        "utf8_filesystem":"YES",
        "chroot_list_enable":"NO",
    }
    def __init__(this,service_name):
        super().__init__(service_name,config_file="/etc/vsftpd.conf")

    def _patch_configuration(this):
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
            trans = RemoteCommandLineTransaction(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
                SOCK_PATH,
                cmd
            )

            trans.run()
            #os.remove(patch_fname)

    def enable(this,*args,**kwargs):
        this._patch_configuration()
        this.start()

    def disable(this,*args,**kwargs):
        this.stop()