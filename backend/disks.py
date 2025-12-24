from backend.config import ConfigMixin
from cmdl import LSBLK
from disk import DiskStatus, Disk
import json

class DiskMixin(ConfigMixin):
    def get_system_disks(this):
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
                 status=None
                )
            for d in sata_disks
        ]

    def get_pool_disks(this):
        pool_disks = this._cfg['pool'].get("disks", [])


        return [
            Disk(
                name=d['name'],
                model=d['model'],
                serial=d['serial'],
                size=d['size'],
                path=d['path'],
                status=None
            )
            for d in pool_disks
        ]


    def get_disks(this):
        pool_disks = this.get_pool_disks()
        system_disks = this.get_system_disks()

        detected_disks = list(set(system_disks).intersection(set(pool_disks)))


        #check if any disk is new
        for disk in system_disks:
            if (disk not in detected_disks):
                disk.status = DiskStatus.NEW
                detected_disks.append(disk)
            else:
                #TODO: check with zpool if the disk is corrupted/faulted
                for d in detected_disks:
                    if d == disk:
                        d.status = DiskStatus.ONLINE
                        break


        #detect if a disk is offline
        for disk in pool_disks:
            if (disk not in detected_disks):
                disk.status = DiskStatus.OFFLINE
                detected_disks.append(disk)



        detected_disks.sort(key=lambda x : x.path)


        return detected_disks