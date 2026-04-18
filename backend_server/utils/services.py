from .responses import ErrorMessage
from backend_server.utils.cmdl import ChPasswd, SystemCtlUnmask, SystemCtlEnable, SystemCtlStart, SystemCtlDisable
from backend_server.utils.cmdl import RestoreContext
from backend_server.utils.cmdl import SELinuxManagePort, Firewall, CommandLine, SELinuxSetBool, SELinuxManageContext
from backend_server.utils.cmdl import Touch, Chmod, UserModAddGroup, GPasswdRemoveGroup, LocalCommandLineTransaction
from backend_server.utils.cmdl import SystemCtlIsActive, ApplyPatch,  GetEntShadow, UserModChangeShell, UserDel
from backend_server.utils.cmdl import SystemCtlMask, SystemCtlStop, ExportfsRA, SMBPasswd, Cat, SystemCtlRestart
from backend_server.utils.inet import PortRange, GenericTransportPort, str2port, TransportProtocol
from backend_server.utils.enums import DistroFamilies
from fastapi import HTTPException
from nms_shared.enums import UserPermissions
from nms_shared.msg import ErrorMessages
from nms_shared.utils import make_diff_from_file, read_lines_from_file, make_diff
from pathlib import Path
from typing import Optional, Callable, List, Any, Self, Tuple
import configparser
import io
import os.path
import re
import subprocess
import tempfile
import time
import threading


class SystemService:
    def __init__(this,service_name:Optional[str]=None, config_file:Optional[str]=None,**kwargs):
        this._service_name = service_name
        this._config_file = config_file
        this._change_hooks = {}
        this._pre_start_hooks = []
        this._permission_hook:Optional[UserPermissions] = None
        this._os_family = kwargs.get('os', DistroFamilies.DEB)

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
    def os_family(this) -> DistroFamilies:
        return this._os_family

    @property
    def service_names(this) -> str:
        return this._service_name

    @property
    def config_file(this) -> str:
        return this._config_file

    @config_file.setter
    def config_file(this,new_value:str)->None:
        this._config_file = new_value

    @property
    def properties(this) -> List[str]:
        return [k for k in this.__class__.__annotations__.keys()]

    def get(this,property:str) -> Any:
        return getattr(this,f"get_{property}")()

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
            services = ', '.join(names)
            errors = "\n".join([o['stderr'] for o in results])
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_SYSTEMD_START.name,params=[services,errors]))

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
            if (not trans.success):
                services = ', '.join(names)
                errors = "\n".join([o['stderr'] for o in results])
                raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_SYSTEMD_STOP.name,
                                                                         params=[services, errors]))

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

        cmd = Cat(this.config_file,sudo=True).execute()

        if (cmd.returncode == 0):
            for line in cmd.stdout.splitlines():
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
        else:
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_READ_FILE.name,params=[this.config_file]))

        return port


    def set_port(this,new_port) -> None:
        old_port = this.get("port")

        cmd = Cat(this.config_file, sudo=True).execute()

        if (cmd.returncode == 0):
            orig_lines = cmd.stdout.splitlines(keepends=True)
        else:
            raise HTTPException(status_code=500,
                                detail=ErrorMessage(code=ErrorMessages.E_READ_FILE.name, params=[this.config_file]))

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

        patch_text = make_diff(this.config_file,orig_lines, mod_lines)

        patch_fname = os.path.join(tempfile.gettempdir(),f"sshd_config.patch")
        Path(patch_fname).write_text(patch_text, encoding="utf-8", errors="surrogateescape")

        cmds:List[CommandLine] = [ApplyPatch(patch_fname,this.config_file)]

        if (this.os_family == DistroFamilies.RH):

            if (old_port != 22):
                cmds.append(SELinuxManagePort(
                    action = SELinuxManagePort.SEManagePortActions.REMOVE,
                    type = "ssh_port_t",
                    port = old_port,
                ))

            cmds.append(
                SELinuxManagePort(
                    action = SELinuxManagePort.SEManagePortActions.ADD,
                    type = "ssh_port_t",
                    port = new_port
                )
            )

            firewall_cmd = Firewall(Firewall.FirewallAction.STATE,sudo=True).execute()
            if ((firewall_cmd.returncode == 0) and (firewall_cmd.stdout.strip() == "running")):
                cmds.extend([
                    Firewall(
                        Firewall.FirewallAction.ADD_PORT,
                        port = new_port
                    ),
                    Firewall(
                        Firewall.FirewallAction.REMOVE_PORT,
                        port=old_port
                    ),
                    Firewall(Firewall.FirewallAction.RELOAD)
                ])



        trans = LocalCommandLineTransaction(*cmds,privileged=True)
        out = trans.run()

        # os.remove(patch_fname)

        if (not trans.success):
            error = "\n".join([o['stderr'] for o in out])
            raise HTTPException(500,detail=ErrorMessage(code=ErrorMessages.E_ACCESS_PROP.value,params=["port",error]))


    def set_password(this,username:str,new_password:str) -> None:
        shadow_cmd = GetEntShadow(username)

        trans = LocalCommandLineTransaction(shadow_cmd)
        output = trans.run()

        if (len(output)!=1):
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_USER_NOT_FOUND.name,params=[username]))

        stdout_getent = output[0].get("stdout","")

        if (len(stdout_getent)==0):
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_USER_NOT_FOUND.name, params=[username]))
        else:

            stdout_token = stdout_getent.split(":")
            uname = stdout_token[0].strip()
            shadow_password = stdout_token[1].strip()

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

    CONF_DEB = '/etc/vsftpd.conf'
    CONF_RH = '/etc/vsftpd/vsftpd.conf'

    PASV_PORTS = PortRange(30000,31000)

    default_configuration={
        "anonymous_enable":"NO",
        "local_enable": "YES",
        "write_enable": "YES",
        "ftpd_banner": "Welcome to NMS FTP Service.",
        "chroot_local_user":"NO",
        "userlist_enable": "YES",
        "userlist_file": USERLIST_FILE,
        "userlist_deny": "NO",
        "chroot_list_enable":"NO",
        "pasv_min_port": str(PASV_PORTS.port_min),
        "pasv_max_port": str(PASV_PORTS.port_min),
        "pasv_enable": "YES",
    }
    def __init__(this,service_name, **kwargs):
        super().__init__(service_name,**kwargs)

        match(this.os_family):
            case DistroFamilies.RH:
                conf = FTPService.CONF_RH
            case _:
                conf = FTPService.CONF_DEB

        this.config_file = conf

        this._permission_hook = UserPermissions.SERVICES_FTP_ACCESS

    def _patch_configuration(this) -> None:
        cfg = FTPService.default_configuration.copy()
        cmd = Cat(this.config_file,sudo=True).execute()

        if (cmd.returncode != 0):
            raise HTTPException(status_code=500,
                                detail=ErrorMessage(code=ErrorMessages.E_ACCESS_ENABLED.name, params=['FTP',cmd.stderr]))

        orig_lines = cmd.stdout.splitlines(keepends=True)
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
            patch_text = make_diff(this.config_file, orig_lines, mod_lines)

            patch_fname = os.path.join(tempfile.gettempdir(), f"vsftpd.patch")
            Path(patch_fname).write_text(patch_text, encoding="utf-8", errors="surrogateescape")

            cmd = ApplyPatch(patch_fname, this.config_file, sudo=True)
            trans = LocalCommandLineTransaction(cmd)

            out = trans.run()
            os.remove(patch_fname)

            if (not trans.success):
                error = "\n".join([o['stderr'] for o in out])
                raise HTTPException(500,
                                    detail=ErrorMessage(code=ErrorMessages.E_ACCESS_PROP.value, params=["port", error]))


    def _setup_firewall(this):
        firewall_cmd = Firewall(Firewall.FirewallAction.STATE, sudo=True).execute()
        if ((firewall_cmd.returncode == 0) and (firewall_cmd.stdout.strip() == "running")):
            cmds = [
                Firewall(
                    Firewall.FirewallAction.ADD_SERVICE,
                    service="ftp"
                ),
                Firewall(
                    Firewall.FirewallAction.ADD_PORT,
                    port=FTPService.PASV_PORTS
                ),
                Firewall(Firewall.FirewallAction.RELOAD),
                SELinuxSetBool("ftpd_full_access",True),
                SELinuxSetBool("ftpd_use_passive_mode", True),
            ]

            trans = LocalCommandLineTransaction(*cmds,privileged=True)
            out = trans.run()

            if (not trans.success):
                error = "\n".join([o['stderr'] for o in out])
                raise HTTPException(500,detail=ErrorMessage(code=ErrorMessages.E_ACCESS_ENABLED.name,params=["FTP",error]))

    def _unsetup_firewall(this):
        firewall_cmd = Firewall(Firewall.FirewallAction.STATE, sudo=True).execute()
        if ((firewall_cmd.returncode == 0) and (firewall_cmd.stdout.strip() == "running")):
            cmds = [
                Firewall(
                    Firewall.FirewallAction.REMOVE_SERVICE,
                    service="ftp"
                ),
                Firewall(
                    Firewall.FirewallAction.REMOVE_PORT,
                    port=FTPService.PASV_PORTS
                ),
                Firewall(Firewall.FirewallAction.RELOAD),
                SELinuxSetBool("ftpd_full_access", False),
                SELinuxSetBool("ftpd_use_passive_mode", False),
            ]

            trans = LocalCommandLineTransaction(*cmds,privileged=True)
            out = trans.run()

            if (not trans.success):
                error = "\n".join([o['stderr'] for o in out])
                raise HTTPException(500,detail=ErrorMessage(code=ErrorMessages.E_ACCESS_DISABLED.name,params=["FTP",error]))

    def enable(this,*args,**kwargs) -> None:
        this._patch_configuration()
        this._setup_firewall()
        this.start()

    def disable(this,*args,**kwargs) -> None:
        this.stop()
        this._unsetup_firewall()

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
    domain:str
    default_options = ['rw','sync','fsid=0']

    IDMAPD_CONFIG = "/etc/idmapd.conf"

    def __init__(this,service_name:str,mountpoint:Optional[str]=None,**kwargs):
        super().__init__(service_name,"/etc/exports",**kwargs)
        this._mountpoint = mountpoint

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
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_NO_CONF.name))

        exports = read_lines_from_file(this.config_file)
        new_exports = exports.copy()

        options = NFSService.default_options.copy()

        new_line = f"{this.mountpoint}\t{hostname}({','.join(options)})\n"

        for i,l in enumerate(exports):
            if (not l.startswith("#")):
                if (this.mountpoint in l):
                    new_exports[i] = new_line
                    break
        else:
            new_exports.append(new_line)

        patch_text = make_diff_from_file(this.config_file, new_exports)

        patch_fname = os.path.join(tempfile.gettempdir(), f"exports.patch")
        Path(patch_fname).write_text(patch_text, encoding="utf-8", errors="surrogateescape")

        cmd = ApplyPatch(patch_fname, this.config_file, sudo=True)
        trans = LocalCommandLineTransaction(cmd)

        trans.run()
        os.remove(patch_fname)

    def get_domain(this) -> Optional[str]:
        idmapd = read_lines_from_file(NFSService.IDMAPD_CONFIG)

        domain = None

        regex = re.compile(r"\s*[#]?\s*domain\s+=\s+(.*)",re.IGNORECASE)

        for l in idmapd:
            if (match := regex.match(l)):
                domain = match.group(1).strip()
                break

        return domain

    def set_domain(this,domain) -> None:
        if (this.mountpoint is None):
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_NO_CONF.name))

        config = configparser.ConfigParser()
        config.read(NFSService.IDMAPD_CONFIG)

        config["General"] = {
            'Domain': domain,        }

        new_output = io.StringIO()
        config.write(new_output)

        modified_file = new_output.getvalue()
        new_output.close()

        modified_lines = modified_file.splitlines(keepends=True)

        patch_text = make_diff_from_file(NFSService.IDMAPD_CONFIG, modified_lines)

        patch_fname = os.path.join(tempfile.gettempdir(), f"idmapd.conf.patch")
        Path(patch_fname).write_text(patch_text, encoding="utf-8", errors="surrogateescape")

        cmd = ApplyPatch(patch_fname, NFSService.IDMAPD_CONFIG, sudo=True)
        trans = LocalCommandLineTransaction(cmd)

        trans.run()
        os.remove(patch_fname)

    def _setup_firewall(this,remove:bool=False) -> None:
        firewall_cmd = Firewall(Firewall.FirewallAction.STATE, sudo=True).execute()
        if ((firewall_cmd.returncode != 0) or (firewall_cmd.stdout.strip() != "running")):
            return

        firewall_action = Firewall.FirewallAction.REMOVE_SERVICE if remove else Firewall.FirewallAction.ADD_SERVICE
        cmds = [
            Firewall(firewall_action,service="nfs",permanent=True),
            Firewall(Firewall.FirewallAction.RELOAD),
            RestoreContext(this.mountpoint),
            SELinuxSetBool("nfs_export_all_rw",not remove),
            SELinuxSetBool("nfs_export_all_ro", False),
            SELinuxSetBool("use_nfs_home_dirs", not remove),
        ]

        trans = LocalCommandLineTransaction(*cmds,privileged=True)
        out = trans.run()

        if (not trans.success):
            errors = "\n".join([o['stderr'] for o in out])
            error_code = ErrorMessages.E_ACCESS_DISABLED if remove else ErrorMessages.E_ACCESS_ENABLED
            raise HTTPException(status_code=500, detail=ErrorMessage(code=error_code.name, params=['NFS', errors]))

    def _unsetup_firewall(this) -> None:
        this._setup_firewall(True)

    def enable(this,ip:str,domain:Optional[str]=None,**kwargs) -> None:
        this.set("ip",ip)
        # this.set("domain",domain)
        this._setup_firewall()
        this.start()

    def start(this) -> None:
        trans = LocalCommandLineTransaction(ExportfsRA())

        trans.run()
        super().start()

    def disable(this,*args,**kwargs) -> None:
        this.stop()
        this._unsetup_firewall()

    def update(this,ip,domain,**kwargs) -> None:
        this.disable()
        this.enable(ip,domain,**kwargs)


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
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_NO_CONF.name))

        config = configparser.ConfigParser()
        config.read(this.config_file)

        config[SMBService.SECTION] = {
            'path': this.mountpoint,
            'valid users': "@sambashare",
            'writable': "yes"
        }

        new_output = io.StringIO()
        config.write(new_output)

        modified_file = new_output.getvalue()
        new_output.close()

        modified_lines = modified_file.splitlines(keepends=True)

        patch_text = make_diff_from_file(this.config_file, modified_lines)

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
        cmd = SMBPasswd(username=username, flag=SMBPasswd.Flags.DISABLE)
        trans = LocalCommandLineTransaction(cmd)
        trans.run()

    def delete_user(this,username) -> None:
        cmd = SMBPasswd(username=username, flag=SMBPasswd.Flags.DELETE)
        trans = LocalCommandLineTransaction(cmd)
        trans.run()

    @staticmethod
    def _get_ports() -> List[Tuple[str,GenericTransportPort]]:
        suffix = "d_port_t"
        selinux_types = ['smb'+suffix,'nmb'+suffix]

        cmd = SELinuxManagePort(SELinuxManagePort.SEManagePortActions.LIST, sudo=True).execute()

        if (cmd.returncode != 0):
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_SELINUX_PORT.name,params=[cmd.stderr]))

        regex = re.compile(r"^[a-zA-Z0-9_]+[ ]+(tcp|udp)[ ]+(.*)$",re.IGNORECASE)

        ports = []
        for l in cmd.stdout.splitlines():
            for type in selinux_types:
                if (type in l):
                    match = regex.match(l)

                    if (match is not None):
                        proto = match.group(1)
                        port = match.group(2)

                        for p in port.split(","):
                            ports.append((proto,str2port(p)))

        return ports

    def _setup_firewall(this,remove:bool=False) -> None:
        firewall_cmd = Firewall(Firewall.FirewallAction.STATE, sudo=True).execute()
        if ((firewall_cmd.returncode != 0) or (firewall_cmd.stdout.strip() != "running")):
            return

        ports = SMBService._get_ports()

        firewall_action = Firewall.FirewallAction.REMOVE_PORT if remove else Firewall.FirewallAction.ADD_PORT
        selinux_action = SELinuxManageContext.SELinuxManageContextActions.REMOVE if remove else SELinuxManageContext.SELinuxManageContextActions.ADD

        cmds = [ Firewall(firewall_action,p[1],protocol=TransportProtocol(p[0])) for p in ports ]
        cmds.extend([
            Firewall(Firewall.FirewallAction.RELOAD),
            SELinuxManageContext(selinux_action,"home_root_t",this.mountpoint),
            SELinuxManageContext(selinux_action, "user_home_dir_t", f"{this.mountpoint}/(.*)"),
            SELinuxManageContext(selinux_action, "user_home_t", f"{this.mountpoint}/(.*)(/.*)+"),
            RestoreContext(this.mountpoint),
            SELinuxSetBool("samba_enable_home_dirs",not remove)
        ])

        trans = LocalCommandLineTransaction(*cmds,privileged=True)
        out = trans.run()

        if (not trans.success):
            errors = "\n".join([o['stderr'] for o in out])
            error_code = ErrorMessages.E_ACCESS_DISABLED if remove else ErrorMessages.E_ACCESS_ENABLED
            raise HTTPException(status_code=500, detail=ErrorMessage(code=error_code.name, params=['SMB', errors]))

    def _unsetup_firewall(this) -> None:
        this._setup_firewall(True)

    def enable(this,**kwargs) -> None:
        this._patch_configuration()
        this._setup_firewall()
        this.start()

    def disable(this,**kwargs) -> None:
        this.stop()
        this._unsetup_firewall()

    def permission_granted(this, username: str) -> None:
        UserModAddGroup(username,"sambashare").execute()

    def permission_revoked(this, username: str) -> None:
        GPasswdRemoveGroup(username,"sambashare").execute()

    def remove_user(this, username: str, **kwargs) -> None:
        this.permission_revoked(username)

#
class WEBService(SystemService):
    NGINX_BLOCKS = ['/box','/api/']
    CONF_DEB = '/etc/nginx/sites-enabled/nms'
    CONF_RH = '/etc/nginx/conf.d/nms.conf'

    def __init__(this,*args,**kwargs):
        super().__init__(*args,**kwargs)

        match(this.os_family):
            case DistroFamilies.RH:
                conf = WEBService.CONF_RH
            case _:
                conf = WEBService.CONF_DEB

        this.config_file = conf



    def _read_config_file(this) -> List[str]:
        c = Cat(this.config_file,sudo=True).execute()

        if (c.returncode != 0):
            raise HTTPException(status_code=500,
                                detail=ErrorMessage(code=ErrorMessages.E_READ_FILE.name,
                                                  params=[this.config_file,c.stderr]
                                    )
                                )

        return c.stdout.splitlines(keepends=True)

    def _apply_patch(this, new_config:List[str]) -> None:
        patch_text = make_diff_from_file(this.config_file, new_config)

        patch_fname = os.path.join(tempfile.gettempdir(), f"nms_nginx.patch")
        Path(patch_fname).write_text(patch_text, encoding="utf-8", errors="surrogateescape")

        cmd = ApplyPatch(patch_fname, this.config_file, sudo=True)
        trans = LocalCommandLineTransaction(cmd)

        trans.run()
        os.remove(patch_fname)

    def _restart_service(this) -> None:
        def _worker():
            time.sleep(1)
            SystemCtlRestart(this.service_names).execute()

        t = threading.Thread(target=_worker)
        t.start()



    def enable(this,**kwargs):
        start_decommenting = False
        new_config_file = []

        for l in this._read_config_file():
            if (not start_decommenting):
                if (any([((p in l) and ("location" in l)) for p in this.NGINX_BLOCKS])):
                    start_decommenting = True

            if (start_decommenting):
                if (l.strip().startswith("#")):
                    l = l.lstrip().lstrip("#")
                if ("}" in l):
                    start_decommenting = False

            new_config_file.append(l)

        this._apply_patch(new_config_file)
        this._restart_service()

    def disable(this,**kwargs):
        start_commenting = False
        new_config_file = []

        for l in this._read_config_file():
            if (not start_commenting):
                if (any([((p in l) and ("location" in l)) for p in this.NGINX_BLOCKS])):
                    start_commenting = True

            if (start_commenting):
                if (not l.strip().startswith("#")):
                    l = f"#{l}"
                if ("}" in l):
                    start_commenting = False

            new_config_file.append(l)



        this._apply_patch(new_config_file)
        this._restart_service()


    @property
    def is_active(this) -> bool:
        found = []

        for l in this._read_config_file():
            if (any([((p in l) and ("location" in l)) for p in this.NGINX_BLOCKS])):
                if (l.strip().startswith("#")):
                    found.append(l)

        return len(found) == 0