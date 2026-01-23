
from constants import SOCK_PATH
from backend_server.utils.cmdl import LSBLK, WipeFS, RemoteCommandLineTransaction, ZPoolLabelClear
from disk import DiskStatus, Disk
from typing import List
import json
import socket



class DiskMixin:

    @staticmethod
    def get_system_disks() -> List[Disk]:
        lsblk = LSBLK()
        lsblk_output = lsblk.execute()
        lsblk_disks = json.loads(lsblk_output.stdout)

        sata_disks = [x for x in lsblk_disks['blockdevices'] if x['tran'] in ['sata','spi']]

        return [
            Disk(name=d['name'],
                 model=d['model'],
                 serial=d['serial'],
                 size=d['size'],
                 path=d['path'],
                 status=DiskStatus.NEW,
                )
            for d in sata_disks
        ]

    def get_disks(this) -> List[Disk]:

        pool_disks = this.get_pool_disks()
        system_disks = this.get_system_disks()

        detected_disks = []

        for sys_disk in system_disks:
            for pool_disk in pool_disks:
                if (sys_disk==pool_disk):
                    detected_disks.append(pool_disk)


        for d in detected_disks:
            pool_disks.remove(d)
            system_disks.remove(d)

        detected_disks.extend(system_disks)
        detected_disks.extend(pool_disks)

        detected_disks.sort(key=lambda x : x.physical_paths)

        return detected_disks

    def _format_disk(this,device:str)-> None:

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            ZPoolLabelClear(device),
        )

        trans.run()

        if (not trans.success):
            trans = RemoteCommandLineTransaction(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
                SOCK_PATH,
                WipeFS(device),
            )

            output = trans.run()

            if (not trans.success):
                raise Exception(output[0].get("stderr", None))

    def format_disk(this,device:str)->None:
        pool = this.pool_name
        this.detach()

        this._format_disk(device)

        this.import_pool(pool,False)


    def smart_info(this, device:str)->dict:
        message = {
            "action": "smart-info",
            "args": {"device": device},
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

        return json.loads(response.decode())