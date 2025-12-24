from abc import abstractmethod
from backend.config import ConfigMixin
from backend.pool import PoolMixin
from cmdl import RemoteCommandLineTransaction, ZFSList, ZFSUnmount, ZFSLoadKey, ZFSUnLoadKey, ZFSMount, CommandLine, \
    ZFSCreate, ZFSDestroy
from constants import SOCK_PATH
from typing import List, Optional
import json
import socket


class DatasetMixin (PoolMixin):

    @property
    def dataset_name(this) -> Optional[str]:
        return this._cfg.get("dataset", None)

    @property
    def mountpoint(this) -> Optional[str]:
        cmd = ZFSList(properties=['mountpoint'])

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            cmd
        )
        output = trans.run()

        if (len(output) == 1):
            d = json.loads(output[0].get("stdout", {}))
            tank = this.pool_name
            dataset = this.dataset_name

            if ((tank is not None) and (dataset is not None)):
                return d.get('datasets', {}).get(f"{tank}/{dataset}", {}).get("properties", {}).get("mountpoint",
                                                                                                    {}).get("value",
                                                                                                            None)
            return None
        else:
            raise Exception("Could not be determined the mountpoint")

    @property
    def is_mounted(this):
        cmd = ZFSList(properties=['mounted'])

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            cmd
        )
        output = trans.run()

        if (len(output) == 1):
            d = json.loads(output[0].get("stdout", {}))
            tank = this.pool_name
            dataset = this.dataset_name


            if ((tank is not None) and (dataset is not None)):
                mounted = d.get('datasets', {}).get(f"{tank}/{dataset}", {}).get("properties", {}).get("mounted",
                                                                                                       {}).get("value",
                                                                                                               "no")
                return mounted.lower() != "no"
            return False
        else:
            raise Exception("Could not be determined if the disk array is mounted")

    def mount(this):
        if (not this.is_pool_configured()):
            raise Exception("Disk array not configured")

        cmds = []

        if (this.has_encryption):
            cmds.append(ZFSLoadKey(this.pool_name, this.key_filename))

        cmds.append(ZFSMount(this.pool_name))
        cmds.append(ZFSMount(this.pool_name, this.dataset_name))

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            *cmds
        )

        output = trans.run()

        if (not trans.success):
            error = "\n".join([o['stderr'] for o in output])
            raise Exception(f"Unable to mount disk array: {error}")



    def unmount(this):
        if (not this.is_pool_configured()):
            raise Exception("Disk array not configured")

        this.disable_all_access_services()

        cmds:List[CommandLine] = [
            ZFSUnmount(this.pool_name,this.dataset_name),
            ZFSUnmount(this.pool_name)
        ]

        if (this.has_encryption):
            cmds.append(ZFSUnLoadKey(this.pool_name))

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            *cmds
        )

        output = trans.run()

        if (not trans.success):
            error = "\n".join([o['stderr'] for o in output])
            raise Exception(f"Unable to unmount disk array: {error}")

    def simulate_format(this):
        if (not this.is_pool_configured()):
            raise Exception("Disk array not configured")

        this.disable_all_access_services()

        try:
            this.unmount()
        except:
            ...

        tank = this.pool_name
        dataset = this.dataset_name

        commands = [
            ZFSDestroy(tank, dataset),
            ZFSCreate(tank, dataset)
        ]

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            *commands
        )
        output = trans.run()

        if (not trans.success):
            errors = "\n ".join([x["stderr"] for x in output])
            raise Exception(errors)

    def rm_mountpoint(this, mountpoint):
        if (this.is_pool_configured()):
            raise Exception("Disk array is configured")

        if (this.is_mounted):
            raise Exception("Disk array is already mounted")

        message = {
            "action": "rm-mountpoint",
            "args": {"mountpoint": mountpoint}
        }

        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(SOCK_PATH)

        s.sendall(json.dumps(message, default=lambda x: x.to_dict()).encode() + b'\n')

        response = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
            if b"\n" in chunk:
                break

        s.close()