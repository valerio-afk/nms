import subprocess
import time

class RevertableCommandLine:

    def __init__(this, command, revert_command = None, tag=None, sudo=False):
        this._command = command
        this._revert_command = revert_command
        this._tag = tag
        this._sudo = sudo

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


class ZPoolLabelClear(RevertableCommandLine):

    def __init__(this,disks):
        cmd = ["zpool","labelclear"]+disks
        super().__init__(cmd,sudo=True)

class ZPoolCreate(RevertableCommandLine):
    def __init__(this,disks,redudancy,encryption,compression,tank_name="tank"):
        cmd = ["zpool", "create",
               "-f" #force
               "-o", "ashift=12" #block alignment
            ]

        if (compression):
            cmd.extend(["-O", "compression=lz4",])

        if (encryption is not None):
            cmd.extend(["-O", "encryption=aes-256-gcm"])
            cmd.extend(["-O", "keyformat=raw"])
            cmd.extend(["-O", f"keylocation=file://{encryption}"])

        cmd.append(tank_name)

        if (redudancy):
            cmd.append("raidz1")

        cmd.extend(disks)

        cmd_revert = ["sudo","zpool","-f","destroy",tank_name]

        super().__init__(cmd,cmd_revert,sudo=True)

class ZFSCreate(RevertableCommandLine):

    def __init__(this,tank="tank", dataset_name="data"):
        cmd = ["zfs","create",f"{tank}/{dataset_name}"]
        cmd_revert = ["sudo", "zfs", "destroy", f"{tank}/{dataset_name}"]

        super().__init__(cmd,cmd_revert,sudo=True)

class ZpoolScrub(RevertableCommandLine):
    def __init__(this,tank):
        super().__init__(['zpool','scrub',tank],sudo=True)


class CreateKey(RevertableCommandLine):
    def __init__(this,key_path="/root/tank.key",bytes=32):
        cmd = [ "dd", "if=/dev/urandom", f"of={key_path}", f"bs={bytes}","count=1"]
        super().__init__(cmd,sudo=True)

class Chmod(RevertableCommandLine):
    def __init__(this,flags,path,sudo=False):
        cmd = ["sudo","chmod",str(flags),path]

        super().__init__(cmd,sudo=sudo)


class CommandLineTransaction:
    def __init__(this, *args):
        this._cmds = [x for x in args]

        this._success = None

    @property
    def success(this):
        return this._success

    def execute(this):
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

        return outputs