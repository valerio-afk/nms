from abc import abstractmethod, ABC
from backend_server.utils.inet import TransportProtocol, GenericTransportPort
from enum import Enum
from subprocess import CompletedProcess
from tempfile import gettempdir
from typing import Optional, List, Dict, Any, Union, Literal
import json
import os
import socket
import subprocess
import time



class CommandLine(ABC):
    def __init__(this,command:List[str],
                 sudo:bool=False,
                 mask_output:bool=False,
                 cwd:Optional[str]=None,
                 wait:Optional[int]=0):
        this._command = command
        this._sudo = sudo
        this._mask_output=mask_output
        this._cwd = os.getcwd() if cwd is None else cwd
        this._wait = wait

    def append(this,cmd):
        if (isinstance(cmd,list) or (isinstance(cmd,tuple))):
            this._command.extend([x for x in cmd])
        elif (isinstance(cmd,str)):
            this._command.append(cmd)
        else:
            raise TypeError("The `cmd` parameter must be either a list or a string")

    @property
    def command(this) -> List[str]:
        return this._command

    @property
    def cwd(this) ->str:
        return this._cwd

    @property
    def mask_output(this) -> bool:
        return this._mask_output


    def _execute(this,raw_cmd) -> Optional[CompletedProcess[str]]:

        if (raw_cmd is None):
            return None

        if (this._sudo):
            raw_cmd = ["sudo"] + raw_cmd

        output = subprocess.run(raw_cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                cwd=this.cwd)

        if (this._wait is not None):
            time.sleep(this._wait)

        return output

    def execute(this,**kwargs)-> Optional[CompletedProcess[str]]:
        return this._execute(this.command)

    def to_dict(this) -> Dict[str,Any]:
        return {"__class__":this.__class__.__name__}

    def to_json(this) -> Dict[str,Any]:
        return this.to_dict()

    @staticmethod
    @abstractmethod
    def from_dict(serialisation):
        pass


class RevertibleCommandLine(CommandLine):
    def __init__(this, command, revert_command = None,**kwargs):
        super().__init__(command,**kwargs)

        this._revert_command = revert_command


    @property
    def revert_command(this):
        return this._revert_command

    def execute(this,revert=False,**kwargs):
        cmd = this.command if not revert else this.revert_command
        return this._execute(cmd)




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

class ZPoolAttach(ZPoolCommand):

    def __init__(this,tank,vdev,device):
        this._tank = tank
        this._vdev = vdev
        this._device = device

        super().__init__("attach",sudo=True)

        this.append([tank,vdev,device])

    def to_dict(this):
        d = super().to_dict()
        d['tank'] = this._tank
        d['vdev'] = this._vdev
        d['device'] = this._device
        return d

    @staticmethod
    def from_dict(serialisation):
        return ZPoolAttach(
            serialisation.get('tank', None),
            serialisation.get("vdev", None),
            serialisation.get("device",None)
        )

class ZPoolReplace(ZPoolCommand):

    def __init__(this,tank:str,device:str,new_device:Optional[str]=None):
        this._tank = tank
        this._device = device
        this._new_device = new_device

        super().__init__("replace",sudo=True)

        this.append([tank,device])

        if (new_device is not None):
            this.append(new_device)

    def to_dict(this):
        d = super().to_dict()
        d['tank'] = this._tank
        d['device'] = this._device
        d['new_device'] = this._new_device
        return d

    @staticmethod
    def from_dict(serialisation):
        return ZPoolAttach(
            serialisation.get('tank', None),
            serialisation.get("device",None),
            serialisation.get("new_device", None)
        )

class ZPoolAdd(ZPoolCommand):

    def __init__(this, tank,  device):
        this._tank = tank
        this._device = device

        super().__init__("add", sudo=True)

        this.append([tank, device])

    def to_dict(this):
        d = super().to_dict()
        d['tank'] = this._tank
        d['device'] = this._device
        return d

    @staticmethod
    def from_dict(serialisation):
        return ZPoolAdd(
            serialisation.get('tank', None),
            serialisation.get("device", None)
        )


class ZPoolDestroy(ZPoolCommand):
    def __init__(this,tank_name="tank",force=True):
        super().__init__("destroy",sudo=True)

        this._tank_name = tank_name
        this._force = force

        if (force):
            this.append("-f")

        this.append(tank_name)

    def to_dict(this):
        d = super().to_dict()
        d['tank_name'] = this._tank_name
        d['force'] = this._force
        return d

    @staticmethod
    def from_dict(serialisation):
        return ZPoolDestroy(serialisation.get('tank_name',None),serialisation.get("force",False))

class ZPoolImport(ZPoolCommand):
    def __init__(this, pool_name:Optional[str] = None, force:bool=False,**kwargs):
        revert = None
        this._pool_name = pool_name
        this._force = force

        if (pool_name is not None):
            revert = ['zpool','export', pool_name]

        super().__init__("import", sudo=True,revert_command=revert,**kwargs)

        if (pool_name is not None):
            this.append(pool_name)

            if (force):
                this.append("-f")

    def to_dict(this):
        d = super().to_dict()
        d['pool_name'] = this._pool_name
        d['force'] = this._force

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZPoolImport(
            serialisation.get('pool_name',None),
            serialisation.get('force', None)
        )

class ZPoolExport(ZPoolCommand):
    def __init__(this,tank_name):

        this._tank_name = tank_name
        revert = ['zpool','import',tank_name]

        super().__init__("export", sudo=True,revert_command=revert)

        this.append(tank_name)

    def to_dict(this):
        d = super().to_dict()
        d['tank_name'] = this._tank_name

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZPoolExport(serialisation.get('tank_name',None))

class ZPoolCreate(ZPoolCommand):
    def __init__(this,disks,redundancy,encryption,compression,tank_name="tank"):
        cmd_revert = ["sudo", "zpool", "destroy", "-f", tank_name]

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
    def __init__(this,subcommand:str,pool:Optional[str]=None,show_json=True,**kwargs):
        super().__init__(subcommand=subcommand, **kwargs)
        this._pool = pool
        this._show_json = show_json

        if (show_json):
            this.append(['-p', '-j'])

        if (pool is not None):
            this.append(this._pool)

    def to_dict(this):
        d = super().to_dict()

        d['pool'] = this._pool
        d['show_json'] = this._show_json

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZPoolScrub(serialisation.get('pool', None))

class ZPoolScrub(ZPoolCommand):
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
        return ZPoolScrub(serialisation.get('pool', None))

class ZPoolClear(ZPoolCommand):
    def __init__(this, pool:str, recovery_mode:bool=False,**kwargs):
        super().__init__(subcommand="clear", sudo=True,**kwargs)
        this._pool = pool
        this._recovery_mode = recovery_mode

        if (recovery_mode):
            this.append(["-F"])

        this.append(this._pool)

    def to_dict(this):
        d = super().to_dict()
        d['pool'] = this._pool
        d['recovery_mode'] = this._recovery_mode
        return d

    @staticmethod
    def from_dict(serialisation):
        return ZPoolClear(serialisation.get('pool', None),
                          serialisation.get('recovery_mode', False))



class ZPoolList(ZpoolJsonSubCommand):
    def __init__(this, pool,**kwargs):
        super().__init__(subcommand="list",pool=pool,sudo=False,**kwargs)

class ZPoolStatus(ZpoolJsonSubCommand):
    def __init__(this, pool:Optional[str]=None,**kwargs):
        super().__init__(subcommand="status",pool=pool,sudo=False,**kwargs)

class ZpoolGet(ZpoolJsonSubCommand):
    def __init__(this, pool,**kwargs):
        super().__init__(subcommand="get",pool=None,sudo=False,**kwargs)
        this._pool = pool

        this.append(["all", pool])



class ZFSCommand(RevertibleCommandLine):
    def __init__(this, subcommand,**kwargs):
        this._disks = None
        cmd = ["zfs", subcommand]
        super().__init__(cmd,**kwargs)

class ZFSGetQuota(ZFSCommand):
    def __init__(this, pool:str,dataset:str,**kwargs):
        super().__init__("userspace",**kwargs)

        this.append(['-p','-H','-o','name,used,quota',f"{pool}/{dataset}"])

        this._pool = pool
        this._dataset = dataset

    def to_dict(this):
        d = super().to_dict()
        d['pool'] = this._pool
        d['dataset'] = this._dataset
        return d

    @staticmethod
    def from_dict(serialisation):
        return ZFSGetQuota(serialisation.get('pool'),serialisation.get("dataset"))


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

class ZFSSetQuota(ZFSCommand):
    def __init__(this, username:str,quota:Union[str,int],pool:str,dataset:str,**kwargs):
        super().__init__("set",**kwargs)

        this.append(f"userquota@{username}={quota}")
        this.append(f"{pool}/{dataset}")

        this._pool = pool
        this._dataset = dataset
        this._username = username
        this._quota = quota

    def to_dict(this):
        d = super().to_dict()
        d['pool'] = this._pool
        d['dataset'] = this._dataset
        d['username'] = this._username
        d['quota'] = this._quota
        return d

    @staticmethod
    def from_dict(serialisation):
        return ZFSSetQuota(
            serialisation.get('username', None),
            serialisation.get('quota', None),
            serialisation.get('pool', None),
            serialisation.get('dataset',None)
        )


class ZFSList(ZFSCommand):
    def __init__(this,
                 properties:List[str]=None,
                 type:Optional[Literal["filesystem","snapshot","volume","bookmark","all"]]=None):
        super().__init__("list", sudo=False)
        this.append(['-p','-j'])

        if (properties is not None):
            this.append("-o")
            this.append([",".join(properties)])

        if (type is not None):
            this.append(["-t",type])

        this._properties = properties

    def to_dict(this):
        d = super().to_dict()
        d['properties'] = this._properties
        return d

    @staticmethod
    def from_dict(serialisation):
        return ZFSList(serialisation.get("properties",None))


class ZFSLoadKey(ZFSCommand):

    def __init__(this,pool="tank",key_path=None):
        this._pool = pool
        this._key_path = key_path

        cmd_revert = ["sudo", "zfs", "unload-key", pool]

        super().__init__("load-key", revert_command=cmd_revert, sudo=True)

        this.append([pool,"-L",f"file://{key_path}"])

    def to_dict(this):
        d = super().to_dict()

        d['pool'] = this._pool
        d['key_path'] = this._key_path

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZFSLoadKey(serialisation.get('pool',None))

class ZFSUnLoadKey(ZFSCommand):
    def __init__(this,pool="tank"):
        this._pool = pool

        super().__init__("unload-key", sudo=True)

        this.append(pool)

    def to_dict(this):
        d = super().to_dict()

        d['pool'] = this._pool

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZFSUnLoadKey(serialisation.get('pool',None))

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

class ZFSDestroy(ZFSCommand):

    def __init__(this, pool:str="tank", dataset:str="data",snapshot_name:Optional[str]=None):
        this._pool = pool
        this._dataset = dataset
        this._snapshot_name = snapshot_name

        fs = f"{pool}/{dataset}"

        if (snapshot_name is not None):
            fs += f"@{snapshot_name}"

        super().__init__("destroy", sudo=True)

        this.append(fs)

    def to_dict(this):
        d = super().to_dict()

        d['pool'] = this._pool
        d['dataset'] = this._dataset
        d['snapshot_name'] = this._snapshot_name

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZFSDestroy(serialisation.get('pool',None),serialisation.get('dataset',None),serialisation.get('snapshot_name',None))

class ZFSRollback(ZFSCommand):

    def __init__(this, pool:str, dataset:str,snapshot_name:str):
        this._pool = pool
        this._dataset = dataset
        this._snapshot_name = snapshot_name

        fs = f"{pool}/{dataset}@{snapshot_name}"

        super().__init__("rollback", sudo=True)

        this.append(['-r',fs])

    def to_dict(this):
        d = super().to_dict()

        d['pool'] = this._pool
        d['dataset'] = this._dataset
        d['snapshot_name'] = this._snapshot_name

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZFSDestroy(serialisation.get('pool',None),serialisation.get('dataset',None),serialisation.get('snapshot_name',None))


class ZFSSnapshot(ZFSCommand):

    def __init__(this, pool:str, dataset:str,snapshot_name:str):
        this._pool = pool
        this._dataset = dataset

        fs = f"{pool}/{dataset}@{snapshot_name}"

        super().__init__("snapshot", sudo=True)

        this.append(fs)

    def to_dict(this):
        d = super().to_dict()

        d['pool'] = this._pool
        d['dataset'] = this._dataset

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZFSSnapshot(serialisation.get('pool',None),serialisation.get('dataset',None))

class ZFSMount(ZFSCommand):

    def __init__(this,pool="tank", dataset=None):
        this._pool = pool
        this._dataset = dataset

        fs = f"{pool}/{dataset}" if dataset is not None else pool

        cmd_revert = ["sudo", "zfs", "unmount", fs]

        super().__init__("mount", revert_command=cmd_revert, sudo=True)

        this.append(fs)

    def to_dict(this):
        d = super().to_dict()

        d['pool'] = this._pool
        d['dataset'] = this._dataset

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZFSMount(serialisation.get('pool',None),serialisation.get('dataset',None))

class ZFSUnmount(ZFSCommand):

    def __init__(this,pool="tank", dataset=None):
        this._pool = pool
        this._dataset = dataset

        fs = f"{pool}/{dataset}" if dataset is not None else pool

        cmd_revert = ["sudo", "zfs", "mount", fs]

        super().__init__("unmount", revert_command=cmd_revert, sudo=True)

        this.append(fs)

    def to_dict(this):
        d = super().to_dict()

        d['pool'] = this._pool
        d['dataset'] = this._dataset

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZFSUnmount(serialisation.get('pool',None),serialisation.get('dataset',None))

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
    def __init__(this,path:str,perm:str,flags:Optional[List[str]]=None,sudo=False):
        this._perm = perm
        this._path = path
        this._flags = flags

        revert_cmd = None

        try:
            current_mode = os.stat(path).st_mode

            revert_cmd = ["chmod"]
            if (flags is not None):
                revert_cmd.extend(flags)
            revert_cmd += [str(oct(current_mode)),path]
        except PermissionError:
            ...

        cmd = ["chmod"]
        if (flags is not None):
            cmd.extend(flags)
        cmd+=[perm,path]
        super().__init__(cmd,revert_command=revert_cmd,sudo=sudo)

    def to_dict(this):
        d:Dict[str,Any] = super().to_dict()

        d['flags'] = this._flags
        d['perm'] = this._perm
        d['path'] = this._path
        d['sudo'] = this._sudo

        return d

    @staticmethod
    def from_dict(serialisation):
        return Chmod(serialisation.get('flags',None),serialisation.get('path',None),sudo=serialisation.get('sudo',False))

class Chown(RevertibleCommandLine):
    def __init__(this,uid:Optional[str|int],gid:Optional[str|int],path:str,flags:Optional[List[str]]= None,sudo=False):
        this._uid = uid
        this._gid = gid
        this._path = path
        this._flags = flags

        cmd = ["chown"]
        if (flags is not None):
            cmd.extend(flags)
        cmd+=[f"{uid or ''}:{gid or ''}",path]

        revert_cmd = None

        try:
            current_uid = os.stat(path).st_uid
            current_gid = os.stat(path).st_gid

            revert_cmd = ["chown"]
            if (flags is not None):
                revert_cmd.extend(flags)
            revert_cmd += [f"{current_uid}:{current_gid}",path]
        except PermissionError:
            ...

        super().__init__(cmd,revert_command=revert_cmd,sudo=sudo)

    def to_dict(this):
        d = super().to_dict()

        d['uid'] = this._uid
        d['gid'] = this._gid
        d['path'] = this._path
        d['flags'] = this._flags
        d['sudo'] = this._sudo

        return d

    @staticmethod
    def from_dict(serialisation):
        return Chown(
            serialisation.get('uid',None),
            serialisation.get('gid', None),
            serialisation.get('path',None),
            sudo=serialisation.get('sudo',False))

class CommandLineTransaction:
    class Hooks(Enum):
        PRE_RUN = 0
        PRE_COMMAND =1
        POST_COMMAND =2
        POST_RUN = 3

    def __init__(this, *args, privileged:bool = False):
        this._cmds = [x for x in args]
        this._success = None

        if (privileged):
            for c in this._cmds:
                c._sudo = True

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

    def run(this) -> List[dict]:
        outputs = []
        failed = False

        this._invoke_hooks(CommandLineTransaction.Hooks.PRE_RUN)

        for t in this._cmds:
            this._invoke_hooks(CommandLineTransaction.Hooks.PRE_COMMAND,command=t,revert=False)
            o = t.execute()
            masked_output = subprocess.CompletedProcess(args=o.args,
                                        returncode=o.returncode,
                                        stdout=o.stdout if not t.mask_output else "*"*5,
                                        stderr=o.stderr if not t.mask_output else "*"*5)
            this._invoke_hooks(CommandLineTransaction.Hooks.POST_COMMAND, output=masked_output)

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
        s.settimeout(20)
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

        try:
            this._success = sum([o['returncode'] for o in outputs]) == 0
            this._invoke_hooks(CommandLineTransaction.Hooks.POST_RUN,outputs=outputs)
        except TypeError as e:
            raise Exception(outputs)

        return outputs



class Shutdown(CommandLine):
    def __init__(this):
        super().__init__(['shutdown','-h','now'],sudo =True)

    @staticmethod
    def from_dict(_):
        return Shutdown()


class Reboot(CommandLine):
    def __init__(this):
        super().__init__(['reboot'], sudo=True)

    @staticmethod
    def from_dict(_):
        return Reboot()

class JournalCtl(CommandLine):
    def __init__(this,service:str, grep:Optional[str]=None,since:Optional[str]=None,until:Optional[str]=None):
        this._service = service
        this._grep = grep

        cmd = ['journalctl','-u',service,'-o','cat']

        if (grep is not None):
            cmd.extend(['--grep',grep])

        if (since is not None):
            cmd.extend(['--since',since])

        if (until is not None):
            cmd.extend(['--until',until])

        super().__init__(cmd,sudo=True,mask_output=True)

    def to_dict(this):
        d = super().to_dict()

        d['service'] = this._service
        d['grep'] = this._grep

        return d

    @staticmethod
    def from_dict(serialisation):
        return JournalCtl(serialisation.get('service',None),serialisation.get('grep',None))

class SystemCtl(RevertibleCommandLine):
    def __init__(this, service, *params,**kwargs):
        this._service = service
        this._params = list(params)

        cmd = ['systemctl'] + this._params + [service]

        super().__init__(cmd, **kwargs, sudo=True)

    def to_dict(this):
        d = super().to_dict()
        d['service'] = this._service
        d['params'] = this._params
        return d

    @staticmethod
    def from_dict(serialisation):
        return SystemCtlRestart(serialisation.get('service', None))

class SystemCtlRestart(SystemCtl):
    def __init__(this,service):
        super().__init__(service,"restart")

    def to_dict(this):
        d = CommandLine.to_dict(this)
        d['service'] = this._service
        return d

    @staticmethod
    def from_dict(serialisation):
        return SystemCtlRestart(serialisation.get('service',None))

class SystemCtlIsActive(SystemCtl):
    def __init__(this,service):
        super().__init__(service,"is-active")

    def to_dict(this):
        d = RevertibleCommandLine.to_dict(this)
        d['service'] = this._service
        return d

    @staticmethod
    def from_dict(serialisation):
        return SystemCtlIsActive(serialisation.get('service',None))

class SystemCtlUnmask(SystemCtl):
    def __init__(this,service):
        super().__init__(service,"unmask",revert_command=["systemctl","mask",service])

    def to_dict(this):
        d = RevertibleCommandLine.to_dict(this)
        d['service'] = this._service
        return d

    @staticmethod
    def from_dict(serialisation):
        return SystemCtlUnmask(serialisation.get('service',None))

class SystemCtlMask(SystemCtl):
    def __init__(this,service):
        super().__init__(service,"mask",revert_command=["systemctl","unmask",service])

    def to_dict(this):
        d = RevertibleCommandLine.to_dict(this)
        d['service'] = this._service
        return d

    @staticmethod
    def from_dict(serialisation):
        return SystemCtlMask(serialisation.get('service',None))



class SystemCtlEnable(SystemCtl):
    def __init__(this, service):
        super().__init__(service, "enable", revert_command=["systemctl", "disable", service])

    def to_dict(this):
        d = RevertibleCommandLine.to_dict(this)
        d['service'] = this._service
        return d

    @staticmethod
    def from_dict(serialisation):
        return SystemCtlEnable(serialisation.get('service', None))

class SystemCtlDisable(SystemCtl):
    def __init__(this, service):
        super().__init__(service, "disable", revert_command=["systemctl", "enable", service])

    def to_dict(this):
        d = RevertibleCommandLine.to_dict(this)
        d['service'] = this._service
        return d

    @staticmethod
    def from_dict(serialisation):
        return SystemCtlDisable(serialisation.get('service', None))



class SystemCtlStart(SystemCtl):
    def __init__(this, service):
        super().__init__(service, "start", revert_command=["systemctl", "stop", service])

    def to_dict(this):
        d = RevertibleCommandLine.to_dict(this)
        d['service'] = this._service
        return d

    @staticmethod
    def from_dict(serialisation):
        return SystemCtlStart(serialisation.get('service', None))

class SystemCtlStop(SystemCtl):
    def __init__(this, service):
        super().__init__(service, "stop", revert_command=["systemctl", "start", service])

    def to_dict(this):
        d = RevertibleCommandLine.to_dict(this)
        d['service'] = this._service
        return d

    @staticmethod
    def from_dict(serialisation):
        return SystemCtlStop(serialisation.get('service', None))



class LSBLK(CommandLine):

    def __init__(this):
        super().__init__(command=["lsblk", "-J", "-b", "-o", "NAME,MODEL,SERIAL,TYPE,TRAN,SIZE,PATH"],sudo=False)

    @staticmethod
    def from_dict(_):
        return LSBLK

class ApplyPatch(RevertibleCommandLine):
    BACK_EXT = ".bkp"

    def __init__(this, patch_file, file_to_patch=None, sudo=True):
        super().__init__(["patch",file_to_patch],sudo=sudo)
        this._file_to_patch = file_to_patch
        this._patch_file = patch_file

    def to_dict(this):
        d = super().to_dict()
        d['patch_file'] = this._patch_file
        d['file_to_patch'] = this._file_to_patch
        d['sudo'] = this._sudo

        return d

    def execute(this,revert=False):
        return this._forward_exec() if not revert else this._backward_exec()

    def _forward_exec(this):
        if (this._file_to_patch is not None):
            backup_filename = os.path.join(gettempdir(),f"{this._file_to_patch}{ApplyPatch.BACK_EXT}")
            subprocess.run(["cp", this._file_to_patch, backup_filename])

        cmd = this._command

        if (this._sudo):
            cmd = ["sudo"] + cmd

        with open(this._patch_file,"r") as h:
            return subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE, stdin = h, text=True)

    def _backward_exec(this):
        if (this._file_to_patch is not None):
            backup_filename = os.path.join(gettempdir(),f"{this._file_to_patch}{ApplyPatch.BACK_EXT}")
            return subprocess.run(["cp", backup_filename, this._file_to_patch], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        else:
            return None


    @staticmethod
    def from_dict(serialisation):
        return ApplyPatch(
            serialisation.get('patch_file',None),
            serialisation.get('file_to_patch', None),
            serialisation.get('sudo', True)
        )

class UserModChangeUsername(RevertibleCommandLine):
    def __init__(this,old,new):
        cmd = ['usermod', '-l', new, old]
        revert_cmd = ['usermod', '-l', old, new]
        super().__init__(cmd,revert_cmd,sudo=True)

        this._old = old
        this._new = new

    def to_dict(this):
        d = super().to_dict()
        d['old'] = this._old
        d['new'] = this._new

        return d

    @staticmethod
    def from_dict(serialisation):
        return UserModChangeUsername(
            serialisation.get('old',None),
            serialisation.get('new', None),
        )

class GroupModChangeGroupName(RevertibleCommandLine):
    def __init__(this,old,new):
        cmd = ['groupmod', '-n', new, old]
        revert_cmd = ['groupmod', '-n', old, new]
        super().__init__(cmd,revert_cmd,sudo=True)

        this._old = old
        this._new = new

    def to_dict(this):
        d = super().to_dict()
        d['old'] = this._old
        d['new'] = this._new

        return d

    @staticmethod
    def from_dict(serialisation):
        return GroupModChangeGroupName(
            serialisation.get('old',None),
            serialisation.get('new', None),
        )

class UserModAddGroup(RevertibleCommandLine):
    def __init__(this,username:str,group:str):
        cmd = ['usermod','-aG',group,username]
        revert_cmd = ['gpasswd', '-d', username, group]
        super().__init__(cmd,revert_cmd,sudo=True)

        this._username = username
        this._group = group

    def to_dict(this):
        d = super().to_dict()
        d['username'] = this._username
        d['group'] = this._group

        return d

    @staticmethod
    def from_dict(serialisation):
        return UserModAddGroup(
            serialisation.get('username',None),
            serialisation.get('group', None),
        )

class UserModChangeShell(RevertibleCommandLine):
    def __init__(this, username: str, shell: str):
        cmd = ['usermod', '-s', shell, username]
        super().__init__(cmd, sudo=True)

        this._username = username
        this._shell = shell

    def to_dict(this):
        d = super().to_dict()
        d['username'] = this._username
        d['shell'] = this._shell

        return d

    @staticmethod
    def from_dict(serialisation):
        return UserModChangeShell(
            serialisation.get('username', None),
            serialisation.get('shell', None),
        )

class GPasswdRemoveGroup(RevertibleCommandLine):
    def __init__(this,username:str,group:str):
        cmd = ['gpasswd', '-d', username, group]
        revert_cmd = ['usermod', '-aG', group, username]

        super().__init__(cmd, revert_cmd, sudo=True)

        this._username = username
        this._group = group

    def to_dict(this):
        d = super().to_dict()
        d['username'] = this._username
        d['group'] = this._group

        return d

    @staticmethod
    def from_dict(serialisation):
        return GPasswdRemoveGroup(
            serialisation.get('username',None),
            serialisation.get('group', None),
        )


class UserModChangeHomeDir(RevertibleCommandLine):
    def __init__(this,username, old,new):
        cmd = ['usermod', '-d', new, username]
        revert_cmd = ['usermod', '-d', old, username]
        super().__init__(cmd,revert_cmd,sudo=True)

        this._old = old
        this._new = new
        this._username = username

    def to_dict(this):
        d = super().to_dict()

        d['old'] = this._old
        d['new'] = this._new
        d['username'] = this._username

        return d

    @staticmethod
    def from_dict(serialisation):
        return UserModChangeHomeDir(
            serialisation.get("username",None),
            serialisation.get('old',None),
            serialisation.get('new', None),
        )

class UserAdd(RevertibleCommandLine):
    def __init__(this,username:str,groups:List[str],home_dir:Optional[str],allow_login:bool,**kwargs):
        cmd = ['useradd', '-U', '-s']

        if allow_login:
            cmd.append('/bin/bash')
        else:
            cmd.append('/usr/sbin/nologin')

        if (home_dir is not None):
            cmd.extend(['-m','-d',home_dir])

        if (len(groups)>0):
            cmd.extend(['-G', ','.join(groups)])

        cmd.append(username)

        revert_cmd = ['userdel','-r',username]

        super().__init__(cmd,revert_command=revert_cmd,**kwargs)

        this._username = username
        this._groups = groups
        this._allow_login = allow_login

    def to_dict(this):
        d = super().to_dict()

        d['username'] = this._username
        d['groups'] = this._groups
        d['allow_login'] = this._allow_login

    @staticmethod
    def from_dict(serialisation):
        return UserAdd(
            serialisation.get("username", None),
            serialisation.get('groups', []),
            serialisation.get('allow_login', False),
        )

class UserDel(CommandLine):
    def __init__(this,username:str, keep_home:bool=True,**kwargs):
        cmd = ['userdel']

        if (not keep_home):
            cmd.append('-r')

        cmd.append(username)

        kwargs.setdefault('sudo',True)

        super().__init__(cmd,**kwargs)

        this._username = username
        this._keep_home = keep_home

    def to_dict(this):
        d = super().to_dict()

        d['username'] = this._username
        d['keep_home'] = this._keep_home

    @staticmethod
    def from_dict(serialisation):
        return UserDel(
            serialisation.get("username", None),
            serialisation.get("keep_home", None),
        )

class GetUserUID(CommandLine):
    def __init__(this,username:str,**kwargs):
        cmd = ['id', '-u', username]
        super().__init__(cmd,**kwargs)

        this._username = username

    def to_dict(this):
        d = super().to_dict()

        d['username'] = this._username

    @staticmethod
    def from_dict(serialisation):
        return GetUserUID(
            serialisation.get("username", None),
        )

class RenameFile(RevertibleCommandLine):
    def __init__(this,old,new):
        cmd = ['mv', old, new]
        revert_cmd = ['mv', new, old]
        super().__init__(cmd,revert_cmd,sudo=True)

        this._old = old
        this._new = new

    def to_dict(this):
        d = super().to_dict()

        d['old'] = this._old
        d['new'] = this._new

        return d

    @staticmethod
    def from_dict(serialisation):
        return RenameFile(
            serialisation.get('old',None),
            serialisation.get('new', None),
        )

class GetEntShadow(CommandLine):
    def __init__(this,username):
        cmd = ['getent','shadow',username]
        this._username = username

        super().__init__(cmd,sudo=True,mask_output=True)

    def to_dict(this):
        d = super().to_dict()
        d['username'] = this._username

        return d

    @staticmethod
    def from_dict(serialisation):
        return GetEntShadow(
            serialisation.get('username',None),
        )

class GetEntPasswd(CommandLine):
    def __init__(this,username:Optional[str]=None):
        cmd = ['getent','passwd']
        this._username = username

        if (username is not None):
            cmd.append(username)

        super().__init__(cmd,sudo=True,mask_output=True)

    def to_dict(this):
        d = super().to_dict()
        d['username'] = this._username

        return d

    @staticmethod
    def from_dict(serialisation):
        return GetEntShadow(
            serialisation.get('username',None),
        )

class ChPasswd(RevertibleCommandLine):
    def __init__(this,username,new_password,old_shadow=None):
        cmd = ['chpasswd']

        super().__init__(cmd,sudo=True)

        this._username = username
        this._new_password = new_password
        this._old_shadow = old_shadow


    def to_dict(this):
        d = super().to_dict()
        d['username'] = this._username
        d['$new_password'] = this._new_password
        d['$old_shadow'] = this._old_shadow

        return d

    def execute(this,revert=False):
        cmd = this.command
        if revert:
            if (this._old_shadow is None):
                return
            else:
                cmd.append("-e")

        if (this._sudo):
            cmd.insert(0,"sudo")


        input = f"{this._username}:{this._old_shadow if revert else this._new_password}"

        output = subprocess.run(cmd,input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE, text=True)

        return output

    @staticmethod
    def from_dict(serialisation):
        return ChPasswd(
            serialisation.get('username',None),
            serialisation.get('$new_password', None),
            serialisation.get('$old_shadow', None),
        )

class ExportfsRA(CommandLine):
    def __init__(this):
        super().__init__(['exportfs','-ra'],sudo=True)

    @staticmethod
    def from_dict(_):
        return ExportfsRA

class SMBPasswd(CommandLine):

    class Flags(Enum):
        ADD = '-a'
        DELETE = '-x'
        UPDATE = ''
        DISABLE = '-d'
        ENABLE = '-e'


    def __init__(this,username,password=None,flag=Flags.UPDATE):
        this._username=username
        this._password=password
        this._flag = flag if isinstance(flag,SMBPasswd.Flags) else SMBPasswd.Flags(flag)

        super().__init__(['smbpasswd'],sudo=True)

    def to_dict(this):
        d = super().to_dict()
        d['username'] = this._username
        d['$password'] = this._password
        d['flag'] = this._flag.value

        return d

    @staticmethod
    def from_dict(serialisation):
        flag = SMBPasswd.Flags(serialisation.get("flag",""))
        return SMBPasswd(serialisation.get("username",None),serialisation.get("$password",None),flag)

    def execute(this,revert=False):
        if revert:
            return None

        cmd = this.command
        cmd.append(this._flag.value)
        cmd.append(this._username)

        if (this._sudo):
            cmd.insert(0,"sudo")

        input = None if this._flag == SMBPasswd.Flags.DELETE else f"{this._password}\n{this._password}\n"


        cmd = [x for x in cmd if len(x)>0]

        output = subprocess.run(cmd,input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE, text=True)

        return output


class WipeFS(CommandLine):
    def __init__(this,dev,all=True):
        this._dev = dev
        this._all = all

        cmd = ["wipefs"]

        if (all):
            cmd.append("-a")

        cmd.append(dev)

        super().__init__(cmd,sudo=True)

    def to_dict(this):
        d = super().to_dict()
        d['dev'] = this._dev
        d['all'] = this._all

        return d

    @staticmethod
    def from_dict(serialisation):
        return WipeFS(serialisation.get("dev", None), serialisation.get("all", True))

class APTGet(CommandLine):
    def __init__(this,subcommand,flags=None,**kwargs):
        cmd = ['apt-get']

        if (flags is not None):
            cmd+=flags

        cmd.append(subcommand)

        kwargs.setdefault('sudo',True)

        super().__init__(cmd,**kwargs)
        this._subcommand = subcommand
        this._flags = flags

class APTGetUpdate(APTGet):
    def __init__(this):
        super().__init__("update")

    @staticmethod
    def from_dict(_):
        return APTGetUpdate()

class APTGetUpgrade(APTGet):
    def __init__(this,dry_run=False,yes=True):
        flags = []

        if (dry_run):
            flags.append("--just-print")
        elif (yes):
            flags.append("-y")


        super().__init__("upgrade",flags)
        this._yes = yes
        this._dry_run = dry_run

    def to_dict(this):
        d = super().to_dict()
        d['yes'] = this._yes
        d['dry_run'] = this._dry_run

        return d

    @staticmethod
    def from_dict(serialisation):
        return APTGetUpgrade(
            serialisation.get("dry_run",False),
            serialisation.get("yes",True)
        )

class Docker(RevertibleCommandLine):
    def __init__(this,subcommand,flags=None,container_name=None,revert_command=None):
        cmd = ["docker",subcommand]

        if (flags is not None):
            cmd.extend(flags)

        if (container_name is not None):
            cmd.append(container_name)

        super().__init__(cmd,sudo=True,revert_command=revert_command)

        this._container_name = container_name

    def to_dict(this):
        d = super().to_dict()

        d['container_name'] = this._container_name

        return d

class DockerRun(Docker):
    def __init__(this,container_name,
                 mount=None,
                 envvars = None,
                 port_forwarding=None,
                 image_name=None,
                 detach=True,
                 remove=True,
                 restart="no",
                 user=None):

        this._mount = mount
        this._envvars = envvars
        this._port_forwarding=port_forwarding
        this._image_name = image_name
        this._detach = detach
        this._remove = remove
        this._restart = restart
        this._user = user

        flags = []

        if (mount is not None):
            for volume,host_path in mount.items():
                flags.extend(['-v',f"{volume}:{host_path}"])

        if (envvars is not None):
            for k,v in envvars.items():
                flags.extend(['--env',f"{k}={v}"])

        if (port_forwarding is not None):
            for p in port_forwarding:
                flags.extend(['-p',":".join([str(x) for x in p])])

        if (image_name is not None):
            flags.extend(['--name',image_name])

        if (detach):
            flags.append("-d")

        if (remove):
            flags.append('--rm')

        if (restart):
            flags.extend(["--restart",restart])

        if (user):
            if (isinstance(user,str)):
                flags.extend([f'--user={user}'])
            else:
                flags.extend([f'--user={":".join(user)}'])

        revert_cmd = ['docker','stop',image_name] if image_name is not None else None

        super().__init__("run",flags,container_name,revert_command=revert_cmd)

    def to_dict(this):
        d = super().to_dict()
        d['mount'] = this._mount
        d['envvars'] = this._envvars
        d['port_forwarding'] = this._port_forwarding
        d['image_name'] = this._image_name
        d['detach'] = this._detach
        d['remove'] = this._remove
        d['restart'] = this._restart
        d['user'] = this._user

        return d

    @staticmethod
    def from_dict(serialisation):
        return DockerRun(
            serialisation.get("container_name",None),
            serialisation.get("mount", None),
            serialisation.get("envvars", None),
            serialisation.get("port_forwarding", None),
            serialisation.get("image_name", None),
            serialisation.get("detach", True),
            serialisation.get("remove", True),
            serialisation.get("restart", True),
            serialisation.get("user", None),
        )

class DockerStop(Docker):
    def __init__(this,container_name):
        super().__init__("stop",container_name=container_name)

    @staticmethod
    def from_dict(serialisation):
        return DockerStop(
            serialisation.get("container_name",None),
        )

class DockerRemove(Docker):
    def __init__(this,container_name):
        super().__init__("rm",container_name=container_name)

    @staticmethod
    def from_dict(serialisation):
        return DockerStop(
            serialisation.get("container_name",None),
        )


class DockerInspect(Docker):
    def __init__(this,container_name,flags):
        super().__init__(subcommand="inspect",
                         container_name=container_name,
                         flags=flags)
        this._flags = flags

    def to_dict(this):
        d = super().to_dict()
        d['flags'] = this._flags

        return d

    @staticmethod
    def from_dict(serialisation):
        return DockerInspect(
            serialisation.get("container_name",None),
            serialisation.get("flags", None),
        )


class NMCLI(CommandLine):
    def __init__(this,terse:bool=True,**kwargs):
        this._terse = terse

        cmd = ['nmcli','-c','no']

        if (terse):
            cmd.append('-t')

        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['terse'] = this._terse

        return d

    @staticmethod
    def from_dict(serialisation):
        return NMCLI(
            serialisation.get("terse", None),
        )


class NMCLIDevice(NMCLI):
    def __init__(this,subcommand:str,*args,**kwargs):
        super().__init__(**kwargs)
        this.append("device")
        this.append(subcommand)
        this.append(args)

        this._subcommand = subcommand
        this._arguments = args

    def to_dict(this):
        d = super().to_dict()
        d['subcommand'] = this._subcommand
        d['arguments'] = this._arguments

        return d

    @staticmethod
    def from_dict(serialisation):
        args = serialisation.get("arguments", [])
        return NMCLIConnection(
            serialisation.get("subcommand", None),
            *args,
        )

class NMCLIConnection(NMCLI):
    def __init__(this,subcommand:str,*args,**kwargs):
        super().__init__(**kwargs)
        this.append("connection")
        this.append(subcommand)
        this.append(args)

        this._subcommand = subcommand
        this._arguments = args

    def to_dict(this):
        d = super().to_dict()
        d['subcommand'] = this._subcommand
        d['arguments'] = this._arguments

        return d

    @staticmethod
    def from_dict(serialisation):
        args = serialisation.get("arguments", [])
        return NMCLIConnection(
            serialisation.get("subcommand", None),
            *args,
        )

class Groups(CommandLine):
    def __init__(this,username:str,**kwargs):
        super().__init__(["groups",username],**kwargs)

        this._username = username

    def to_dict(this):
        d = super().to_dict()
        d['username'] = this._username

        return d

    @staticmethod
    def from_dict(serialisation):
        return Groups(
            serialisation.get("username", None),
        )

class Touch(RevertibleCommandLine):
    def __init__(this,filename:str,**kwargs):
        cmd = ['touch',filename]
        revert_cmd = ['rm',filename]

        super().__init__(cmd,revert_command=revert_cmd,**kwargs)

        this._filename = filename

    def to_dict(this):
        d = super().to_dict()
        d['filename'] = this._filename

        return d

    @staticmethod
    def from_dict(serialisation):
        return Touch(
            serialisation.get("filename", None),
        )

class RSync(CommandLine):
    def __init__(this,src:str,dest:str,flags:Optional[List[str]]=None,**kwargs):
        cmd = ['rsync']

        if (flags is not None):
            cmd.extend(flags)

        cmd.extend([src,dest])

        super().__init__(cmd,**kwargs)

        this._src = src
        this._dest = dest
        this._flags = flags

    def to_dict(this):
        d = super().to_dict()
        d['src'] = this._src
        d['dest'] = this._dest
        d['flags'] = this._flags

        return d

    @staticmethod
    def from_dict(serialisation):
        return RSync(
            serialisation.get("src", None),
            serialisation.get("dest", None),
            serialisation.get("flags", None),
        )


class Mkdir(RevertibleCommandLine):
    def __init__(this,path:str,parents:bool=False,**kwargs):
        cmd = ['mkdir']
        if parents:
            cmd.append("-p")
        cmd.append(path)

        revert_cmd = ['rmdir',path]

        super().__init__(cmd,revert_cmd,**kwargs)

        this._path = path
        this._parents = parents

    def to_dict(this):
        d = super().to_dict()
        d['path'] = this._path
        d['parents'] = this._parents

        return d

    @staticmethod
    def from_dict(serialisation):
        return Mkdir(
            serialisation.get("path", None),
            serialisation.get("parents", None),
        )

class LS(CommandLine):
    def __init__(this,path:str,all:bool=False,**kwargs):
        cmd = ['ls']

        if (all):
            cmd.append("-a")

        cmd.append(path)

        this._path = path
        this._all = all
        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['path'] = this._path
        d['all'] = this._all

        return d

    @staticmethod
    def from_dict(serialisation):
        return LS(
            serialisation.get("path", None),
            serialisation.get("all", False),
        )

class Stat(CommandLine):
    def __init__(this,filename:str,format:Optional[str]=None,**kwargs):
        cmd = ['stat',filename]
        if (format is not None):
            cmd.extend(["--format",format])

        this._filename = filename
        this._format = format

        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['filename'] = this._filename
        d['format'] = this._format

        return d

    @staticmethod
    def from_dict(serialisation):
        return Stat(
            serialisation.get("filename", None),
            serialisation.get("format", None),
        )

class MimeType(CommandLine):
    def __init__(this,filename:str,**kwargs):
        cmd = ['mimetype',filename]
        this._filename = filename

        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['filename'] = this._filename

        return d

    @staticmethod
    def from_dict(serialisation):
        return MimeType(
            serialisation.get("filename", None),
        )

class Move(RevertibleCommandLine):
    def __init__(this,src:str,dest:str,**kwargs):
        cmd = ['mv',src,dest]
        revert_cmd = ['mv',dest,src]

        this._src = src
        this._dest = dest

        super().__init__(cmd,revert_cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['src'] = this._src
        d['dest'] = this._dest

        return d

    @staticmethod
    def from_dict(serialisation):
        return Move(
            serialisation.get("src", None),
            serialisation.get("dest", None),
        )

class Copy(CommandLine):
    def __init__(this,src:str,dest:str,recursive:bool=False,**kwargs):
        cmd = ['cp']

        if (recursive):
            cmd.append("-r")

        cmd.extend([src,dest])

        this._src = src
        this._dest = dest
        this._recursive = recursive

        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['src'] = this._src
        d['dest'] = this._dest
        d['recursive'] = this._recursive

        return d

    @staticmethod
    def from_dict(serialisation):
        return Copy(
            serialisation.get("src", None),
            serialisation.get("dest", None),
            serialisation.get("recursive",False),
        )



class RemoveFile(CommandLine):
    def __init__(this,path:str,is_dir:bool=False,**kwargs):
        this._path = path
        this._is_dir = is_dir

        cmd = ['rm']

        if (is_dir):
            cmd.append('-rf')

        cmd.append(path)

        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['path'] = this._path
        d['is_dir'] = this._is_dir

        return d

    @staticmethod
    def from_dict(serialisation):
        return RemoveFile(
            serialisation.get("path", None),
            serialisation.get("is_dir", None),
        )


class Cat(CommandLine):
    def __init__(this,filename:str,**kwargs):
        this._filename = filename
        cmd = ['cat',filename]
        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['filename'] = this._filename

        return d

    @staticmethod
    def from_dict(serialisation):
        return Cat(
            serialisation.get("filename", None),
        )


class TarArchive(CommandLine):
    class TarAction(Enum):
        EXTRACT ='x'
        CREATE  ='c'

    class TarCompression(Enum):
        AUTO = 'a'
        BZIP2= 'j'
        XZ   = 'J'
        GZIP = 'z'
    def __init__(this,
                 path:str,
                 archive_filename:str,
                 action:TarAction,
                 compression:Optional[TarCompression]=TarCompression.AUTO,
                 files:Optional[List[str]] = None,
                 exclude:Optional[List[str]]=None,
                 strip_components:Optional[int]=None,
                 **kwargs):

        this._path = path
        this._archive_filename = archive_filename
        this._action = action
        this.compression = compression
        this.exclude = exclude

        flags = f"-{action.value}{compression.value}f"

        cmd = ['tar',flags,archive_filename,'-C', path]

        if (exclude is not None):
            for e in exclude:
                cmd.append(f"--exclude={e}")

        match (action):
            case TarArchive.TarAction.EXTRACT:
                cmd.append(".")
            case TarArchive.TarAction.CREATE:
                cmd.extend(files)

                if (strip_components is not None):
                    cmd.append(f"--strip-components={strip_components}")

        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['path'] = this._path
        d['archive_filename'] = this._archive_filename
        d['action'] = this._action
        d['compression'] = this._compression
        d['exclude'] = this._exclude

        return d

    @staticmethod
    def from_dict(serialisation):
        return TarArchive(
            serialisation.get("path", None),
            serialisation.get("archive_filename", None),
            serialisation.get("action", None),
            serialisation.get("compression", None),
            serialisation.get("exclude", None),
        )


class NPMRun(CommandLine):
    def __init__(this,command:str,**kwargs):
        cmd = ['npm','run',command]
        this._command = command

        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['command'] = this._command

        return d

    @staticmethod
    def from_dict(serialisation):
        return NPMRun(
            serialisation.get("command", None),
        )

class SetfACL(CommandLine):
    class IdentifierType(Enum):
        USER  = 'u'
        GROUP = 'g'

    def __init__(this,identifier:str,
                 path: str,
                 type:IdentifierType=IdentifierType.USER,
                 permissions:str="rwx",
                 mask:Optional[str]=None,
                 recursive:bool=False,
                 default:bool=False,
                 **kwargs):

        this._identifier = identifier
        this._type = type
        this._recursive = recursive
        this._default = default
        this._permissions = permissions
        this._mask = mask

        cmd = ['setfacl']

        if (recursive):
            cmd.append('-R')

        if (default):
            cmd.append('-d')

        cmd.append("-m")

        target = f"{type.value}:{identifier}:{permissions}"

        if (mask is not None):
            target+=f",m:{mask}"

        cmd.extend([target,path])

        kwargs.setdefault("sudo",True)

        super().__init__(cmd, **kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['path'] = this._path
        d['type'] = this._type.value
        d['recursive'] = this._recursive
        d['default'] = this._default
        d['permissions'] = this._permissions
        d['mask'] = this._mask

        return d

    @staticmethod
    def from_dict(serialisation):
        return SetfACL(
            serialisation.get("path", None),
            serialisation.get("type", None),
            serialisation.get("permissions", None),
            serialisation.get("mask", None),
            serialisation.get("recursive", None),
            serialisation.get("default", None),
        )


class Unpack(CommandLine):
    def __init__(this,filename:str,**kwargs):
        cmd = ['unp','-U',filename]
        this._filename = filename

        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['filename'] = this._filename

        return d

    @staticmethod
    def from_dict(serialisation):
        return Unpack(
            serialisation.get("filename", None),
        )

class Zip(CommandLine):
    def __init__(this,zip_file:str,files:List[str],recursive:bool=True,**kwargs):
        cmd = ['zip']

        if (recursive):
            cmd.append('-r')

        cmd.append(zip_file)
        cmd.extend(files)

        this._zip_file = zip_file
        this._files = files
        this._recursive = recursive

        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['zip_file'] = this._zip_file
        d['files'] = this._files
        d['recursive'] = this._recursive

        return d

    @staticmethod
    def from_dict(serialisation):
        return Zip(
            serialisation.get("zip_file", None),
            serialisation.get('files', []),
            serialisation.get('recursive', True),
        )

class SevenZip(CommandLine): #Cannot call this class 7Zip - you know
    class SevenZipAction(Enum):
        EXTRACT ='e'
        CREATE  ='a'

    def __init__(this,zip_file:str,
                 action:SevenZipAction=SevenZipAction.CREATE,
                 files:Optional[List[str]]=None,
                 compression_level:Optional[int]=9,**kwargs):
        cmd = ['7z',action.value]#,,zip_file] + files

        if ((action == SevenZip.SevenZipAction.CREATE) and (compression_level is not None)):
            cmd.append(f'-mx={compression_level}')

        cmd.append(zip_file)

        if ((action == SevenZip.SevenZipAction.CREATE) and (files is not None)):
            cmd.extend(files)

        this._zip_file = zip_file
        this._files = files
        this._compression_level = compression_level
        this._action = action

        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['zip_file'] = this._zip_file
        d['files'] = this._files
        d['compression_level'] = this._compression_level
        d['action'] = this._action

        return d

    @staticmethod
    def from_dict(serialisation):
        return SevenZip(
            serialisation.get("zip_file", None),
            serialisation.get('action', SevenZip.SevenZipAction.CREATE),
            serialisation.get('files', []),
            serialisation.get('compression_level', True),
        )



class SELinuxManage(RevertibleCommandLine):
    def __init__(this,subcommand:str,**kwargs):
        cmd = ['semanage',subcommand]
        super().__init__(cmd,**kwargs)

        this._subcommand = subcommand

    def to_dict(this):
        d = super().to_dict()
        d['subcommand'] = this._subcommand

        return d

class SELinuxManagePort(SELinuxManage):
    class SEManagePortActions(Enum):
        ADD='-a'
        REMOVE='-d'
        EDIT='-m'
        LIST='-l'

    def __init__(this,
                 action:SEManagePortActions,
                 type:Optional[str] = None,
                 port:Optional[int] = None,
                 old_port:Optional[int]=None,
                 protocol: TransportProtocol = TransportProtocol.TCP,
                 **kwargs):

        this._action = action
        this._type = type
        this._port = port
        this._protocol = protocol
        this._old_port = old_port

        cmd = [action.value]
        rev_cmd = ['ls']  # something that has no effect

        if (action == SELinuxManagePort.SEManagePortActions.LIST):
            cmd.append("--noheading")
        else:
            cmd += [
                "-t", type,
                "-p", protocol.value, str(port),
            ]

            match (action):
                case SELinuxManagePort.SEManagePortActions.ADD:
                    rev_cmd = ['semanage',
                               'port',
                               SELinuxManagePort.SEManagePortActions.REMOVE.value,
                               "-t", type,
                               "-p", protocol.value,
                               str(port)]
                case SELinuxManagePort.SEManagePortActions.REMOVE:
                    rev_cmd = ['semanage',
                               'port',
                               SELinuxManagePort.SEManagePortActions.ADD.value,
                               "-t", type,
                               "-p",protocol.value,
                               str(port)]
                case SELinuxManagePort.SEManagePortActions.EDIT:
                    if (old_port is not None):
                        rev_cmd = ['semanage',
                                   'port',
                                   SELinuxManagePort.SEManagePortActions.EDIT.value,
                                   "-t", type,
                                   "-p",protocol.value,
                                   str(old_port)]


        super().__init__("port",revert_command=rev_cmd, **kwargs)

        this.append(cmd)

    def to_dict(this):
        d = super().to_dict()
        d['action'] = this._action
        d['type'] = this._type
        d['port'] = this._port
        d['old_port'] = this._old_port
        d['protocol'] = this._protocol

        return d

    @staticmethod
    def from_dict(serialisation):
        return SELinuxManagePort(
            serialisation.get("action", None),
            serialisation.get('type', None),
            serialisation.get('port', None),
            serialisation.get('old_port', None),
            serialisation.get('protocol', True)
        )

class SELinuxManageContext(SELinuxManage):
    class SELinuxManageContextActions(Enum):
        ADD='-a'
        REMOVE='-d'
        LIST='-l'

    def __init__(this,
                 action:SELinuxManageContextActions,
                 type:Optional[str] = None,
                 file_spec:Optional[str] = None,
                 **kwargs):

        this._action = action
        this._type = type
        this._file_spec = file_spec

        cmd = [action.value]
        rev_cmd = ['ls']  # something that has no effect

        if (action == SELinuxManagePort.SEManagePortActions.LIST):
            cmd.append("--noheading")
        else:
            cmd += ["-t", type,file_spec]

        match (action):
            case SELinuxManagePort.SEManagePortActions.ADD:
                rev_cmd = ['semanage',
                           'port',
                           SELinuxManagePort.SEManagePortActions.REMOVE.value,
                           "-t", type,
                           file_spec]
            case SELinuxManagePort.SEManagePortActions.REMOVE:
                rev_cmd = ['semanage',
                           'port',
                           SELinuxManagePort.SEManagePortActions.ADD.value,
                           "-t", type,
                           file_spec]

        super().__init__("fcontext",revert_command=rev_cmd, **kwargs)

        this.append(cmd)

    def to_dict(this):
        d = super().to_dict()
        d['action'] = this._action
        d['type'] = this._type
        d['file_spec'] = this._file_spec

        return d

    @staticmethod
    def from_dict(serialisation):
        return SELinuxManagePort(
            serialisation.get("action", None),
            serialisation.get('type', None),
            serialisation.get('file_spec', None),
        )

class RestoreContext(CommandLine):
    def __init__(this,path:str,recursive:bool=True,**kwargs):
        cmd = ['restorecon']
        if (recursive):
            cmd.append('-R')

        cmd.append(path)

        this._path = path
        this._recursive = recursive

        super().__init__(cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['path'] = this._path
        d['recursive'] = this._recursive

        return d

    @staticmethod
    def from_dict(serialisation):
        return RestoreContext(
            serialisation.get("path", None),
            serialisation.get("recursive", True),
        )

class SELinuxSetBool(RevertibleCommandLine):
    def __init__(this,property:str,value:bool,permanent:bool=True,**kwargs):
        cmd = ['setsebool']

        if (permanent):
            cmd.append('-P')

        cmd.append(property)

        revert_cmd = cmd.copy()

        cmd.append("1" if value else "0")
        revert_cmd.append("1" if not value else "0")

        super().__init__(cmd,revert_cmd,**kwargs)

        this._property = property
        this._value = value
        this._permanent = permanent

    def to_dict(this):
        d = super().to_dict()
        d['property'] = this._property
        d['value'] = this._value
        d['permanent'] = this._permanent

        return d

    @staticmethod
    def from_dict(serialisation):
        return SELinuxSetBool(
            serialisation.get("property", None),
            serialisation.get("value", None),
            serialisation.get("permanent", True),
        )



class Firewall(RevertibleCommandLine):
    class FirewallAction(Enum):
        ADD_PORT='--add-port'
        REMOVE_PORT='--remove-port'
        ADD_SERVICE = '--add-service'
        REMOVE_SERVICE = '--remove-service'
        RELOAD='--reload'
        STATE = '--state'

    def __init__(this,
                 action:FirewallAction,
                 port:Optional[GenericTransportPort] = None,
                 service:Optional[str] = None,
                 protocol: TransportProtocol = TransportProtocol.TCP,
                 permanent:bool=True,
                 **kwargs):
        cmd = ['firewall-cmd']

        port_configuration = str(port)
        rev_cmd = ['ls']  # inert

        if (action in [Firewall.FirewallAction.RELOAD, Firewall.FirewallAction.STATE]):
            cmd.append(action.value)
        else:

            if (action in [Firewall.FirewallAction.ADD_PORT, Firewall.FirewallAction.REMOVE_PORT]):
                cmd.append(f"{action.value}={port_configuration}/{protocol.value}")
                match(action):
                    case Firewall.FirewallAction.ADD_PORT:
                        rev_cmd = ['firewall-cmd',f"{Firewall.FirewallAction.REMOVE_PORT.value}={port_configuration}/{protocol.value}"]
                    case Firewall.FirewallAction.REMOVE_PORT:
                        rev_cmd = ['firewall-cmd',
                                   f"{Firewall.FirewallAction.ADD_PORT.value}={port_configuration}/{protocol.value}"]
            elif (action in [Firewall.FirewallAction.ADD_SERVICE, Firewall.FirewallAction.REMOVE_SERVICE]):
                cmd.append(f"{action.value}={service}")
                match(action):
                    case Firewall.FirewallAction.ADD_SERVICE:
                        rev_cmd = ['firewall-cmd',f"{Firewall.FirewallAction.REMOVE_SERVICE.value}={service}"]
                    case Firewall.FirewallAction.REMOVE_SERVICE:
                        rev_cmd = ['firewall-cmd',f"{Firewall.FirewallAction.ADD_SERVICE.value}={service}"]

            if (permanent):
                cmd.append("--permanent")
                if (len(rev_cmd) > 1): # more than ls
                    rev_cmd.append("--permanent")

        this._action = action
        this._port = port
        this._protocol = protocol
        this._permanent = permanent

        super().__init__(cmd,rev_cmd,**kwargs)

    def to_dict(this):
        d = super().to_dict()
        d['action'] = this._action
        d['port'] = this._port
        d['protocol'] = this._protocol
        d['permanent'] = this._permanent

        return d

    @staticmethod
    def from_dict(serialisation):
        return Firewall(
            serialisation.get("action", None),
            serialisation.get('port', None),
            serialisation.get('protocol', None),
            serialisation.get('permanent', True)
        )


class DNF(CommandLine):
    def __init__(this,subcommand:str,**kwargs):
        kwargs.setdefault("sudo",True)
        super().__init__(['dnf',subcommand],**kwargs)

class DNFCheckUpdate(DNF):
    def __init__(this,**kwargs):
        super().__init__("check-update",**kwargs)

    def to_dict(this):
        return {}

    @staticmethod
    def from_dict(serialisation):
        return DNFCheckUpdate()

class DNFUpgrade(DNF):
    def __init__(this,**kwargs):
        super().__init__("upgrade",**kwargs)
        this.append(['--refresh','-y'])

    def to_dict(this):
        return {}

    @staticmethod
    def from_dict(serialisation):
        return DNFUpgrade()
