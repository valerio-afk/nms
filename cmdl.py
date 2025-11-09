import json
import subprocess
import socket
import time
import os
from abc import abstractmethod, ABC
from enum import Enum

class RevertibleCommandLine(ABC):
    def __init__(this, command, revert_command = None, tag=None, sudo=False):
        this._command = command
        this._revert_command = revert_command
        this._tag = tag
        this._sudo = sudo

    def append(this,cmd):
        if (isinstance(cmd,list)):
            this._command.extend([x for x in cmd])
        elif (isinstance(cmd,str)):
            this._command.append(cmd)
        else:
            raise TypeError("The `cmd` parameter must be either a list or a string")

    @property
    def command(this):
        return this._command

    @property
    def revert_command(this):
        return this._revert_command

    @property
    def tag(this):
        return this._tag

    def execute(this,revert=False):
        cmd = this.command if not revert else this.revert_command

        if (cmd is None):
            return None

        if (this._sudo):
            cmd = ["sudo"] + cmd

        output = subprocess.run(cmd,stdout=subprocess.PIPE, text=True)
        time.sleep(1)

        return output

    def to_dict(this):
        return {"__class__":this.__class__.__name__}

    def to_json(this):
        return this.to_dict()

    @staticmethod
    @abstractmethod
    def from_dict(serialisation):
        pass


class ZPoolCommand(RevertibleCommandLine):
    def __init__(this, subcommand, **kwargs):
        this._disks = None
        this._flags = None
        cmd = ["zpool", subcommand]

        super().__init__(cmd,**kwargs)


class ZPoolLabelClear(ZPoolCommand):
    def __init__(this,disk):
        this._disk = disk
        super().__init__(subcommand='labelclear',sudo=True)

        this.append(this._disk)

    def to_dict(this):
        d = super().to_dict()
        d['disk'] = this._disk
        return d

    @staticmethod
    def from_dict(serialisation):
        return ZPoolLabelClear(serialisation.get('disk',None))



class ZPoolCreate(ZPoolCommand):
    def __init__(this,disks,redundancy,encryption,compression,tank_name="tank"):
        cmd_revert = ["sudo", "zpool", "-f", "destroy", tank_name]

        super().__init__("create", revert_command=cmd_revert,sudo=True)

        this._redundancy = redundancy
        this._encryption = encryption
        this._compression = compression
        this._tank_name = tank_name
        this._disks = [x for x in disks]

        this.append([
               "-f", #force
               "-o", "ashift=12" #block alignment
            ])

        if (compression):
            this.append(["-O", "compression=lz4"])

        if (encryption is not None):
            this.append(["-O", "encryption=aes-256-gcm"])
            this.append(["-O", "keyformat=raw"])
            this.append(["-O", f"keylocation=file://{encryption}"])

        this.append(tank_name)

        if (redundancy):
            this.append("raidz1")

        if (disks is not None):

            this.append(this._disks)




    def to_dict(this):
        d = super().to_dict()
        d['disks'] = this._disks
        d['redundancy'] = this._redundancy
        d['encryption'] = this._encryption
        d['compression'] = this._compression
        d['tank_name'] = this._tank_name
        return d

    @staticmethod
    def from_dict(serialisation):
        return ZPoolCreate(serialisation.get('disks',[]),
                           serialisation.get('redundancy', False),
                           serialisation.get('encryption', None),
                           serialisation.get('compression', False),
                           serialisation.get('tank_name', None),
                           )


class ZpoolJsonSubCommand(ZPoolCommand):
    def __init__(this,subcommand,pool,**kwargs):
        super().__init__(subcommand=subcommand, **kwargs)
        this._pool = pool

        this.append(['-p', '-j'])

        if (pool is not None):
            this.append(this._pool)

    def to_dict(this):
        d = super().to_dict()

        d['pool'] = this._pool

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZpoolScrub(serialisation.get('pool',None))

class ZpoolScrub(ZPoolCommand):
    def __init__(this, pool):
        super().__init__(subcommand="scrub",sudo=True)
        this._pool = pool

        this.append(this._pool)

    def to_dict(this):
        d = super().to_dict()
        d['pool'] = this._pool
        return d

    @staticmethod
    def from_dict(serialisation):
        return ZpoolScrub(serialisation.get('pool',None))

class ZpoolList(ZpoolJsonSubCommand):
    def __init__(this, pool):
        super().__init__(subcommand="list",pool=pool,sudo=False)

class ZpoolStatus(ZpoolJsonSubCommand):
    def __init__(this, pool):
        super().__init__(subcommand="status",pool=pool,sudo=False)

class ZpoolGet(ZpoolJsonSubCommand):
    def __init__(this, pool):
        super().__init__(subcommand="get",pool=None,sudo=False)
        this._pool = pool

        this.append(["all", pool])



class ZFSCommand(RevertibleCommandLine):
    def __init__(this, subcommand,**kwargs):
        this._disks = None
        cmd = ["zfs", subcommand]
        super().__init__(cmd,**kwargs)


class ZFSGet(ZFSCommand):
    def __init__(this, pool):
        super().__init__("get", sudo=False)
        this.append(['-p','-j','all','tank'])

    def to_dict(this):
        d = super().to_dict()
        d['pool'] = this._pool
        return d

    @staticmethod
    def from_dict(serialisation):
        return ZFSGet(serialisation.get('pool',None))

class ZFSList(ZFSCommand):
    def __init__(this):
        super().__init__("list", sudo=False)
        this.append(['-p','-j'])

    @staticmethod
    def from_dict(_):
        return ZFSList()

class ZFSCreate(ZFSCommand):

    def __init__(this,pool="tank", dataset="data"):
        this._pool = pool
        this._dataset = dataset

        fs = f"{pool}/{dataset}"

        cmd_revert = ["sudo", "zfs", "destroy", fs]

        super().__init__("create", revert_command=cmd_revert, sudo=True)

        this.append(fs)

    def to_dict(this):
        d = super().to_dict()

        d['pool'] = this._pool
        d['dataset'] = this._dataset

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZFSCreate(serialisation.get('pool',None),serialisation.get('dataset',None))




class CreateKey(RevertibleCommandLine):
    def __init__(this,key_path="/root/tank.key",bytes=32):
        cmd = [ "dd", "if=/dev/urandom", f"of={key_path}", f"bs={bytes}","count=1"]
        revert = ["rm", key_path]

        this._key_path = key_path
        this._bytes = bytes

        super().__init__(cmd,revert_command=revert,sudo=True)

    def to_dict(this):
        d = super().to_dict()

        d['key_path'] = this._key_path
        d['bytes'] = this._bytes

        return d

    @staticmethod
    def from_dict(serialisation):
        return CreateKey(serialisation.get('key_path',None),serialisation.get('bytes',0))

class Chmod(RevertibleCommandLine):
    def __init__(this,flags,path,sudo=False):
        this._flags = flags
        this._path = path

        current_mode = os.stat(path).st_mode

        revert_cmd = ["chmod",str(oct(current_mode)),path]

        cmd = ["chmod",flags,path]
        super().__init__(cmd,revert_command=revert_cmd,sudo=sudo)

    def to_dict(this):
        d = super().to_dict()

        d['flags'] = this._flags
        d['path'] = this._path
        d['sudo'] = this._sudo

        return d

    @staticmethod
    def from_dict(serialisation):
        return Chmod(serialisation.get('flags',None),serialisation.get('path',None),sudo=serialisation.get('sudo',False))

class CommandLineTransaction:
    class Hooks(Enum):
        PRE_RUN = 0
        PRE_COMMAND =1
        POST_COMMAND =2
        POST_RUN = 3

    def __init__(this, *args):
        this._cmds = [x for x in args]
        this._success = None

        this._hooks = {
            CommandLineTransaction.Hooks.PRE_RUN : [],
            CommandLineTransaction.Hooks.PRE_COMMAND : [],
            CommandLineTransaction.Hooks.POST_COMMAND : [],
            CommandLineTransaction.Hooks.POST_RUN : []
        }

    @property
    def commands(this):
        return [x for x in this._cmds]

    @property
    def success(this):
        return this._success

    def add_hook_handler(this, handler, hook ):
        this._hooks[hook].append(handler)

    def remove_hook_handler(this, handler, hook ):
        this._hooks[hook].remove(handler)

    def remove_hook_handler_by_id(this,hook,id):
        return this._hooks[hook].pop(id)

    def _invoke_hooks(this,hook,*args,**kwargs):
        for fn in this._hooks[hook]:
            fn(*args,**kwargs)

    @abstractmethod
    def run(this):
        pass

class LocalCommandLineTransaction(CommandLineTransaction):

    def run(this):
        outputs = []
        failed = False

        this._invoke_hooks(CommandLineTransaction.Hooks.PRE_RUN)

        for t in this._cmds:
            this._invoke_hooks(CommandLineTransaction.Hooks.PRE_COMMAND,command=t,revert=False)
            o = t.execute()
            this._invoke_hooks(CommandLineTransaction.Hooks.POST_COMMAND, output=o)

            outputs.append(o)

            if (o.returncode != 0):
                failed=True
                break

        if (failed):
            n = len(outputs)
            this._success = False

            if (n>0):
                for t in this._cmds[(n-1):0:-1]:
                    this._invoke_hooks(CommandLineTransaction.Hooks.PRE_COMMAND,command=t,revert=True)
                    t.execute(revert=True)
                    this._invoke_hooks(CommandLineTransaction.Hooks.POST_COMMAND, output=o)
        else:
            this._success = True

        this._invoke_hooks(CommandLineTransaction.Hooks.POST_RUN,success=this._success,outputs=outputs)

        return [ {"returncode": o.returncode, "stdout":o.stdout, "stderr":o.stderr} for o in outputs ]


class RemoteCommandLineTransaction(CommandLineTransaction):
    def __init__(this, address_family,type, address,*args):
        this._address_family = address_family
        this._type = type
        this._address = address

        super().__init__(*args)

    def run(this):
        this._invoke_hooks(CommandLineTransaction.Hooks.PRE_RUN)

        s = socket.socket(this._address_family, this._type)
        s.settimeout(5)
        s.connect(this._address)


        message = {
            "action": "run",
            "args": {"commands": this.commands}
        }

        s.sendall(json.dumps(message,default=lambda x:x.to_dict()).encode()+b'\n')

        response = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
            if b"\n" in chunk:
                break

        s.close()

        outputs = json.loads(response.decode("utf-8").strip())

        this._success = sum([o['returncode'] for o in outputs]) == 0
        this._invoke_hooks(CommandLineTransaction.Hooks.POST_RUN,outputs=outputs)

        return outputs



class Shutdown(RevertibleCommandLine):
    def __init__(this):
        super().__init__(['shutdown','-h','now'],sudo =True)

    @staticmethod
    def from_dict(_):
        return Shutdown()


class Reboot(RevertibleCommandLine):
    def __init__(this):
        super().__init__(['reboot'], sudo=True)

    @staticmethod
    def from_dict(_):
        return Reboot()

class JournalCtl(RevertibleCommandLine):
    def __init__(this,service, grep=None):
        this._service = service
        this._grep = grep

        cmd = ['journalctl','-u',service,'-o','cat']

        if (grep is not None):
            cmd.extend(['--grep',grep])

        super().__init__(cmd,sudo=True)

    def to_dict(this):
        d = super().to_dict()

        d['service'] = this._service
        d['grep'] = this._grep

        return d

    @staticmethod
    def from_dict(serialisation):
        return JournalCtl(serialisation.get('service',None),serialisation.get('grep',None))

class SystemCtlRestart(RevertibleCommandLine):
    def __init__(this,service):
        this._service = service
        cmd = ['systemctl','restart',service]
        super().__init__(cmd,sudo=True)

    def to_dict(this):
        d = super().to_dict()
        d['service'] = this._service
        return d

    @staticmethod
    def from_dict(serialisation):
        return SystemCtlRestart(serialisation.get('service',None))


class LSBLK(RevertibleCommandLine):

    def __init__(this):
        super().__init__(command=["lsblk", "-J", "-b", "-o", "NAME,MODEL,SERIAL,TYPE,TRAN,SIZE,PATH"],sudo=False)

    @staticmethod
    def from_dict(_):
        return LSBLK