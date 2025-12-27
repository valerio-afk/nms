
from constants import SOCK_PATH
from cmdl import LSBLK, WipeFS, RemoteCommandLineTransaction, ZPoolLabelClear
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

        sata_disks = [x for x in lsblk_disks['blockdevices'] if x['tran'] == 'sata']

        return [
            Disk(name=d['name'],
                 model=d['model'],
                 serial=d['serial'],
                 size=d['size'],
                 path=d['path'],
                 status=DiskStatus.ONLINE,
                )
            for d in sata_disks
        ]

    def get_disks(this) -> List[Disk]:
        pool_disks = this.get_pool_disks()
        system_disks = this.get_system_disks()

        detected_disks = list(set(system_disks).intersection(set(pool_disks)))

        #check if any disk is new
        for disk in system_disks:
            if (disk not in detected_disks):
                disk.status = DiskStatus.NEW
                detected_disks.append(disk)


        #detect if a disk is offline
        for disk in pool_disks:
            if (disk not in detected_disks):
                disk.status = DiskStatus.OFFLINE
                detected_disks.append(disk)



        detected_disks.sort(key=lambda x : x.path)


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
        import_key = this.has_encryption
        this.detach()

        this._format_disk(device)

        this.import_pool(pool,import_key)

