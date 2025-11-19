import os.path
import tempfile
from abc import abstractmethod
from cmdl import RemoteCommandLineTransaction, SystemCtlIsActive, ApplyPatch
from constants import SOCK_PATH
from nms_utils import make_diff, read_lines_from_file
from pathlib import Path
import socket

class SystemService:
    def __init__(this,service_name, config_file=None):
        this._service_name = service_name
        this._config_file = config_file

    @property
    def name(this):
        return this._service_name

    @property
    def config_file(this):
        return this._config_file

    @property
    def properties(this):
        return [k for k in vars(this.__class__) if not k.startswith("__")]

    @abstractmethod
    def get(this,property):
        return getattr(this,f"get_{property}")()

    @abstractmethod
    def set(this, property, value):
        getattr(this,f"set_{property}")(value)

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
            output = results[0]['stdout']
            return output == "active"
        else:
            return False

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

        patch_fname = os.path.join(tempfile.tempdir,f"sshd_config.patch")
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



class DummyService(SystemService):
    def __init__(this):
        super().__init__("dummy!")


SERVICES = {"ssh":SSHService,"sftp":DummyService,"smb":DummyService,"nfs":DummyService,"web":DummyService}