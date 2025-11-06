import json
import subprocess
import socket
import time
import os
from abc import abstractmethod, ABC

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

        print(cmd)

        output = subprocess.run(["ls", "-lah"],stdout=subprocess.PIPE, text=True)
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
    def __init__(this, subcommand, flags=None, disks=None,**kwargs):
        this._disks = None
        this._flags = None
        cmd = ["zpool", subcommand]

        kwargs['sudo'] = True
        super().__init__(cmd,**kwargs)

        if (flags is not None):
            this._flags = [x for x in flags]
            this.append(this._flags)

        if (disks is not None):
            this._disks = [x for x in disks]
            this.append(this._disks)

    def to_dict(this):
        d = super().to_dict()
        d['disks'] = this._disks
        return d


class ZPoolLabelClear(ZPoolCommand):
    def __init__(this,disks):
        super().__init__(subcommand='labelclear',disks=disks)

    @staticmethod
    def from_dict(serialisation):
        return ZPoolLabelClear(serialisation.get('disks',[]))



class ZPoolCreate(ZPoolCommand):
    def __init__(this,disks,redundancy,encryption,compression,tank_name="tank"):
        cmd_revert = ["sudo", "zpool", "-f", "destroy", tank_name]

        this._redundancy = redundancy
        this._encryption = encryption
        this._compression = compression
        this._tank_name = tank_name

        flags = [
               "-f", #force
               "-o", "ashift=12" #block alignment
            ]

        if (compression):
            flags.extend(["-O", "compression=lz4"])

        if (encryption is not None):
            flags.extend(["-O", "encryption=aes-256-gcm"])
            flags.extend(["-O", "keyformat=raw"])
            flags.extend(["-O", f"keylocation=file://{encryption}"])

        flags.append(tank_name)

        if (redundancy):
            flags.append("raidz1")

        super().__init__("create", flags, disks, revert_command=cmd_revert)


    def to_dict(this):
        d = super().to_dict()
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


class ZpoolScrub(ZPoolCommand):
    def __init__(this, pool):
        this._pool = pool
        super().__init__(subcommand="scrub",disks=None)
        this.append(this._pool)

    def to_dict(this):
        d = ZPoolCommand.to_dict(this)
        d['pool'] = this._pool

        return d

    @staticmethod
    def from_dict(serialisation):
        return ZpoolScrub(serialisation.get('pool',None))

class ZFSCommand(RevertibleCommandLine):
    def __init__(this, subcommand,**kwargs):
        this._disks = None
        cmd = ["zfs", subcommand]

        kwargs['sudo'] = True
        super().__init__(cmd,**kwargs)


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
    def __init__(this, *args):
        this._cmds = [x for x in args]
        this._success = None

    @property
    def commands(this):
        return [x for x in this._cmds]

    @property
    def success(this):
        return this._success

    @abstractmethod
    def run(this):
        pass

class LocalCommandLineTransaction(CommandLineTransaction):

    def run(this):
        outputs = []

        failed = False

        for t in this._cmds:
            o = t.execute()

            outputs.append(o)

            if (o.returncode != 0):
                failed=True
                break

        if (failed):
            n = len(outputs)
            this._success = False

            if (n>0):
                for t in this._cmds[(n-1):0:-1]:
                    t.execute(revert=True)
        else:
            this._success = True

        return [ {"returncode": o.returncode, "stdout":o.stdout, "stderr":o.stderr} for o in outputs ]


class RemoteCommandLineTransaction(CommandLineTransaction):
    def __init__(this, address_family,type, address,*args):
        this._address_family = address_family
        this._type = type
        this._address = address

        super().__init__(*args)

    def run(this):
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

        return outputs



