import json
import subprocess
import socket
from tempfile import gettempdir
import os
from abc import abstractmethod, ABC
from enum import Enum

class CommandLine(ABC):
    def __init__(this,command,sudo=False,mask_output=False):
        this._command = command
        this._sudo = sudo
        this._mask_output=mask_output

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
    def mask_output(this):
        return this._mask_output


    def _execute(this,raw_cmd):

        if (raw_cmd is None):
            return None

        if (this._sudo):
            raw_cmd = ["sudo"] + raw_cmd

        output = subprocess.run(raw_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        return output

    def execute(this,**kwargs):
        return this._execute(this.command)

    def to_dict(this):
        return {"__class__":this.__class__.__name__}

    def to_json(this):
        return this.to_dict()

    @staticmethod
    @abstractmethod
    def from_dict(serialisation):
        pass


class RevertibleCommandLine(CommandLine):
    def __init__(this, command, revert_command = None, sudo=False,mask_output=False):
        super().__init__(command,sudo,mask_output)

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
    def __init__(this,properties=None):
        super().__init__("list", sudo=False)
        this.append(['-p','-j'])

        if (properties is not None):
            this.append("-o")
            this.append([",".join(properties)])

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

class Chown(RevertibleCommandLine):
    def __init__(this,uid,gid,path,sudo=False):
        this._uid = uid
        this._gid = gid
        this._path = path

        current_uid = os.stat(path).st_uid
        current_gid = os.stat(path).st_gid

        revert_cmd = ["chown",f"{current_uid}:{current_gid}",path]

        cmd = ["chown",str(uid) if gid is None else f"{uid}:{gid}",path]

        super().__init__(cmd,revert_command=revert_cmd,sudo=sudo)

    def to_dict(this):
        d = super().to_dict()

        d['uid'] = this._uid
        d['gid'] = this._gid
        d['path'] = this._path
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
    def __init__(this,service, grep=None):
        this._service = service
        this._grep = grep

        cmd = ['journalctl','-u',service,'-o','cat']

        if (grep is not None):
            cmd.extend(['--grep',grep])

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

class GetEntShadow(RevertibleCommandLine):
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


class APTGet(CommandLine):
    def __init__(this,subcommand,flags=None):
        cmd = ['apt-get']

        if (flags is not None):
            cmd+=flags

        cmd.append(subcommand)

        super().__init__(cmd,sudo=True)
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
