from cmdl import ZPoolExport, RemoteCommandLineTransaction, ZFSDestroy, ZPoolDestroy, \
    ZPoolList, ZPoolImport, ZPoolCreate, ZFSCreate, CreateKey, \
    ZPoolStatus, ZPoolAdd, ZPoolAttach, LSBLK, ZFSList, ZFSGet, ZFSLoadKey, CommandLine, \
    LocalCommandLineTransaction, ZPoolClear, ZPoolReplace
from constants import SOCK_PATH, KEYPATH
from datetime import timedelta
from disk import DiskStatus, Disk
from flask_babel import _
from msg import ErrorMessage
from typing import Tuple, Optional, List, Dict, Callable
import base64
import json
import os
import re
import socket
import subprocess


remove_partition:Callable[[str],str] = lambda path : re.sub(r"-part[0-9]$","",path)

class PoolMixin:

    def __init__(this, *args,**kwargs) -> None:
        if (not this.is_pool_present() and this.is_pool_configured()):
                this.deconfigure_pool()
        else:
            if (this.is_a_pool_present() and (not this.is_pool_configured())):
                this.init_pool()

        super().__init__(*args, **kwargs)

    @property
    def pool_name(this) -> str:
        return this.cfg['pool'].get("name", None)

    @property
    def has_redundancy(this) -> bool:
        return this.cfg['pool'].get("redundancy",False)

    @property
    def has_encryption(this) -> bool:
        return False if this.cfg['pool'].get("encrypted", None) is None else True

    @property
    def has_compression(this) -> bool:
        return this.cfg['pool'].get("compressed", False)

    @property
    def key_filename(this) -> str:
        return this.cfg['pool'].get("encrypted", None)


    @property
    def get_pool_capacity(this) -> Dict[str, int]:
        if (not this.is_pool_configured()):
            return None

        zpool_list = ZPoolList(this.pool_name)

        output = zpool_list.execute()

        if (output.returncode == 0):
            d = json.loads(output.stdout)

            pool_properties = d.get('pools',{}).get(this.pool_name,{}).get('properties',None)

            if (pool_properties is not None):
                return {
                    "used": int(pool_properties.get('allocated',{}).get('value',0)),
                    "total": int(pool_properties.get('size', {}).get('value', 0))
                }
            else:
                raise Exception(f"Unable to read disk array capacity information: unknown error")
        else:
            raise Exception(f"Unable to read disk array capacity information: {output.returncode}")

    @property
    def get_array_expansion_status(this) -> Tuple[Optional[float], Optional[timedelta], bool]:

        if (not this.is_pool_configured()):
            raise Exception(ErrorMessage.get_error(ErrorMessage.E_POOL_NO_CONF))

        if (not this.has_redundancy):
            return 100.0, timedelta(0), True

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            ZPoolStatus(this.pool_name,show_json=False)
        )

        output = trans.run()

        if (not trans.success):
            raise Exception(f"Unable to get array expansion status: {output[0]['stderr']}")

        zpool_output = output[0]['stdout']

        this.logger.warning(zpool_output)


        # Case 1: percentage + ETA available
        with_eta = re.search(
            r'([\d.]+)%\s+done,\s+([\d:]+)\s+to\s+go',
            zpool_output,
            re.IGNORECASE
        )

        if with_eta:
            pct = float(with_eta.group(1))
            h, m, s = map(int, with_eta.group(2).split(":"))
            return pct, timedelta(hours=h, minutes=m, seconds=s), False

        # Case 2: percentage but ETA explicitly unavailable
        no_eta = re.search(
            r'([\d.]+)%\s+done,.*no\s+estimated\s+time',
            zpool_output,
            re.IGNORECASE
        )

        if no_eta:
            pct = float(no_eta.group(1))
            return pct, None, False

        # case 3: done
        completed = re.search(r'expand:\s+expanded', zpool_output,
            re.IGNORECASE)
        if completed:
            return 100.0, timedelta(0), True

        return None, None, False

    @property
    def get_attachable_disks(this) -> List[Disk]:
        disks = [d for d in this.get_system_disks() if d.status == DiskStatus.NEW]
        config_disk = this.get_pool_disks()

        physical_paths = []

        for d in config_disk:
            physical_paths.extend(d.physical_paths)

        physical_paths = set(physical_paths)
        attachable_disks = []

        for d in disks:

            if (len(physical_paths.intersection(set(d.physical_paths))) == 0):
                attachable_disks.append(d)

        return attachable_disks

    def get_pool_disks(this) -> List[Disk]:
        trans = LocalCommandLineTransaction(ZPoolStatus(this.pool_name))
        output = trans.run()

        if (trans.success) and (len(output) == 1):
            stdout = output[0].get('stdout',None)

            try:
                d = json.loads(stdout)
                pool_name = this.pool_name

                if (this.has_redundancy):
                    disks = d.get("pools",{}) \
                            .get(pool_name,{}) \
                            .get("vdevs",{}) \
                            .get(pool_name,{}) \
                            .get("vdevs",{}) \
                            .popitem()[1] \
                            .get("vdevs",{})
                else:
                    disks = d.get("pools", {}) \
                        .get(pool_name, {}) \
                        .get("vdevs", {}) \
                        .get(pool_name, {}) \
                        .get("vdevs", {})


                paths = [remove_partition(d['path']) for d in disks.values()]

                attached_disks = [ x for x in this.get_system_disks() if x.has_any_paths(paths) ]
                detached_disks = []

                for d in attached_disks:
                    for x in disks.values():
                        path = x.get('path',None)
                        if path is not None:
                            path = remove_partition(path)
                            if d.has_path(path):
                                match (x.get("state")):
                                    case 'ONLINE':
                                        d.status = DiskStatus.ONLINE
                                    case 'OFFLINE':
                                        d.status = DiskStatus.OFFLINE
                                    case _:
                                        d.status = DiskStatus.CORRUPTED

                for d in disks.values():
                    if (d.get("not_present",0)==1) or (d.get("state",None) == "REMOVED"):
                        old_path = d.get("path",None)
                        if path is None:
                            old_path = d.get("was","")

                        old_path = remove_partition(old_path)

                        offline_disk = Disk(
                            name=d.get("name"),
                            model="Removed disk",
                            serial="N/A",
                            size=int(d.get("phys_space","0")),
                            path=d.get("was",""),
                            status=DiskStatus.OFFLINE
                        )

                        for cfg_disk in this.get_configured_disks():
                            if cfg_disk.has_path(old_path):
                                offline_disk.name = cfg_disk.name
                                offline_disk.model = cfg_disk.model
                                offline_disk.serial = cfg_disk.serial
                                offline_disk.size = cfg_disk.size
                                offline_disk.cached_physical_paths = cfg_disk.cached_physical_paths

                        detached_disks.append(offline_disk)


                return attached_disks + detached_disks

            except Exception as e:
                raise Exception(e)

        return []

    def get_pool_options(this) -> List[Tuple[str,bool]]:
        return [
            (_("Redundancy"), this.has_redundancy),
            (_("Encryption"), this.has_encryption),
            (_("Compression"), this.has_compression),
        ]

    def is_pool_configured(this) -> bool:
        return True if this.cfg['pool'].get("name",None) is not None else False

    def is_pool_present(this) -> bool:
        if (not this.is_pool_configured()):
            return False

        trans = LocalCommandLineTransaction(ZPoolStatus(this.pool_name))
        trans.run()

        return trans.success

    def is_a_pool_present(this) -> bool:
        zfs_list = ZFSList()
        zfs_list_output = zfs_list.execute()

        if (zfs_list_output.returncode == 0):
            output = zfs_list_output.stdout
            d = json.loads(output)

            return len(d.get("datasets",{})) > 0

        return False

    def detach(this) -> None:
        if (not this.is_pool_configured()):
            raise Exception("Disk array not configured")

        cmds = [ZPoolExport(this.pool_name)]

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

    def destroy_tank(this) -> None:
        if (not this.is_pool_configured()):
            raise Exception("Disk array not configured")

        this.disable_all_access_services()

        mountpoint = this.mountpoint

        try:
            this.unmount()
        except:
            ...

        tank = this.pool_name
        dataset = this.dataset_name

        commands = [
            ZFSDestroy(tank,dataset),
            ZPoolDestroy(tank)
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

        this.deconfigure_pool()

        this.rm_mountpoint(mountpoint)

    def get_importable_pools(this) -> dict:

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            ZPoolImport(),
        )

        output = trans.run()

        if (not trans.success):
            raise Exception("Unable to get importable pools")

        result = output[0]['stdout']

        pools = []
        current_pool = None
        in_config = False
        read_status_action = False

        for line in result.splitlines():
            line = line.rstrip()

            # pool name
            m = re.match(r"\s*pool:\s+(\S+)", line)
            if m:
                current_pool = {
                    "name": m.group(1),
                    "disks": [],
                    "message": "",
                    "state": None
                }
                pools.append(current_pool)
                in_config = False
                continue

            line = line.strip()

            # start of config section
            if line == "config:":
                in_config = True
                read_status_action = False
                continue

            if (line.startswith("status:") or line.startswith("action:")) and current_pool:
                read_status_action = True
                _,message = line.split(":",1)
                current_pool["message"] += " "+message.strip()
                continue
            elif read_status_action:
                current_pool["message"] += " " + line
                continue

            if (line.startswith("state:") and current_pool):
                _,state = line.split(":",1)
                current_pool["state"] = state.strip()
                continue

            if not in_config or current_pool is None:
                continue


            # disk lines are indented and have ONLINE/DEGRADED/etc
            m = re.match(r"(\S+)\s+(ONLINE|DEGRADED|FAULTED|OFFLINE|UNAVAIL)", line)
            if m:
                dev = m.group(1)

                # skip vdevs like mirror-0, raidz1-0, etc
                if (not re.match(r"(mirror|raidz)\S*", dev)) and (current_pool["name"] not in line):
                    output = subprocess.run(['find','/dev','-name',f"*{dev}"],capture_output=True)

                    if output.returncode == 0:
                        lines = output.stdout.decode('utf8').splitlines()
                        if (len(lines)>0):
                            dev = lines[0].strip()

                            parts = dev.split(os.path.sep)
                            if (len(parts)>2):
                                dev = os.path.realpath(dev)

                    current_pool["disks"].append(dev)

        for d in pools:
            d['message'] = d['message'].strip()

        return pools

    def create_pool(this,
                    poolname:str,
                    datasetname:str,
                    redundancy:bool,
                    encryption:bool,
                    compression:bool,
                    disks:list) -> None:

        if this.is_pool_configured():
            raise Exception(ErrorMessage.get_error(ErrorMessage.E_POOL_ALREADY_CONF))

        disks_objs = [d for d in this.get_disks() if d.status == DiskStatus.NEW]

        if redundancy and (len(disks)<3):
            raise Exception(ErrorMessage.get_error(ErrorMessage.E_POOL_REDUNDANCY_MIN))

        for disk in disks:
            this._format_disk(disk)



        commands = []
        enc_key = None
        if encryption:
            enc_key = KEYPATH
            keygen = CreateKey(enc_key)
            commands.append(keygen)



        commands.append(ZPoolCreate(disks,redundancy,enc_key,compression,poolname))
        commands.append(ZFSCreate(poolname,datasetname))

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            *commands
        )
        output = trans.run()

        if (not trans.success):
            if (len(output)==0):
                raise ErrorMessage.get_error(ErrorMessage.E_UNKNOWN)
            else:
                raise Exception(output[-1].get('stderr',None))

        this.cfg['pool']['name'] = poolname
        this.cfg['dataset'] = datasetname

        if (redundancy):
            this.cfg['pool']['redundancy'] = True

        if (encryption):
            this.cfg['pool']['encrypted'] = enc_key

        if (compression):
            this.cfg['pool']['compressed'] = True

        this.cfg['pool']['disks'] = []

        this.cfg['pool']['disks'] = [d.serialise() for d in disks_objs if d.has_any_paths(disks)]

        this.flush_config()

        this.change_permissions()
        # this._start_tank_observer()

    def get_tank_key(this) -> bytes:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(SOCK_PATH)

        key_fullpath = this.key_filename
        key_path, key_fname = os.path.split(key_fullpath)

        message = {
            "action": "get-key",
            "args": {"fname": key_fname}
        }

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

        d = json.loads(response.decode("utf-8").strip())

        if (d.get('key_path',"") == key_fullpath):
            key = base64.b64decode(d.get("key",""))
            return key

    def import_tank_key(this, handle) -> None:

        base64_bytes = base64.b64encode(handle)
        base64_string = base64_bytes.decode('utf-8')


        message = {
            "action": "import-key",
            "args":
                {
                    "key": base64_string,
                    "filename": KEYPATH
                 }
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

        d = json.loads(response.decode("utf-8").strip())

        if (d is not None):

            error = d.get("error",None)

            if (error is not None):
                raise Exception(error)


    def import_pool(this,poolname,load_key:bool=False) -> None:
        command:List[CommandLine] = [ZPoolImport(poolname)]

        if (load_key):
            command.append(ZFSLoadKey(poolname,KEYPATH))

        trans = RemoteCommandLineTransaction(socket.AF_UNIX,
                                             socket.SOCK_STREAM,
                                             SOCK_PATH, *command)

        output = trans.run()

        if (not trans.success):
            raise Exception(output[0]['stderr'])


        this.init_pool()

        try:
            if (not this.is_mounted):
                this.mount()
        except Exception as e:
            RemoteCommandLineTransaction(socket.AF_UNIX,
                                         socket.SOCK_STREAM,
                                         SOCK_PATH, ZPoolExport(poolname)).run()

            this.load_configuration_file() #revert to previous state

            raise Exception(str(e))


        this.flush_config()





    def init_pool(this) -> None:

        pool_name = None
        dataset_name = None

        zfs_list = ZFSList()
        zfs_list_output = zfs_list.execute()

        if (zfs_list_output.returncode!=0):
            return

        zfs_list_d = json.loads(zfs_list_output.stdout)

        if (len(zfs_list_d)==0):
            return

        datasets = zfs_list_d.get('datasets',{})

        if (len(datasets)<2):
            return

        for dataset in datasets.keys():
            if "/" in dataset:
                pool_name,dataset_name = dataset.split("/")

        if ((pool_name is None) or (dataset_name is None)):
            return


        status = ZPoolStatus(pool_name)
        output = status.execute()

        if (output.returncode==0):
            d = json.loads(output.stdout)

            vdevs = d.get("pools",{}).get(pool_name,{}).get("vdevs",{}).get(pool_name,{}).get("vdevs",{})

            if (len(vdevs)==1):
                # check if raidz is enabled
                value = list(vdevs.keys())[0]

                if (vdevs[value]['vdev_type']=='raidz'):
                    this.cfg['pool']['redundancy'] = True
                    vdevs = vdevs[value].get("vdevs",{})

            if (len(vdevs) > 0):
                disks = [ sd for sd in vdevs.keys() ]
                disks.sort()

                disks_in_pool = []

                lsblk = LSBLK()
                lsblk_output = lsblk.execute()

                if (lsblk_output.returncode != 0):
                    return

                lsblk_json = json.loads(lsblk_output.stdout)
                block_devices = lsblk_json.get("blockdevices",{})

                if (len(block_devices)==0):
                    return

                for dev in disks:
                    for dev_info in block_devices:
                        if dev == dev_info['name']:
                            disk_dev= Disk(name=dev_info['name'],
                                 model=dev_info['model'],
                                 serial=dev_info['serial'],
                                 size=dev_info['size'],
                                 path=dev_info['path'],
                                 status=DiskStatus.ONLINE
                                 )


                            disks_in_pool.append(disk_dev)

                this.cfg['pool']['disks'] = [d.serialise() for d in disks_in_pool]


                this.cfg['pool']['name'] = pool_name
                this.cfg['dataset'] = dataset_name

                pool_properties = ZFSGet(pool_name)
                prop_output = pool_properties.execute()

                if (prop_output.returncode == 0):
                    d_prop = json.loads(prop_output.stdout)
                    pool_properties = d_prop.get('datasets',{}).get(pool_name,{}).get("properties",{})
                    if (len(pool_properties) > 0):
                        # check compression
                        this.cfg['pool']['compressed'] = True if (pool_properties['compression']['value'].lower() != "off") else False
                        # check for encryption
                        enc_enabled = pool_properties['encryption']['value'].lower() != "off"

                        if (enc_enabled):
                            key_location = pool_properties['keylocation']['value']
                            if key_location.startswith("file://"):
                                key_location = key_location[len("file://"):]

                            this.cfg['pool']['encrypted'] = key_location


    def expand_pool(this,new_device:str) -> None:
        cmd = None

        disks = this.get_attachable_disks

        new_disk_obj = [ d for d in disks if d.has_path(new_device)]

        if (len(new_disk_obj)!=1):
            raise Exception(ErrorMessage.get_error(ErrorMessage.E_POOL_EXPAND_INFO, new_device))

        new_disk_obj = new_disk_obj.pop()

        this.disable_all_access_services()
        this.unmount()

        if this.has_redundancy:
            status = ZPoolStatus(this.pool_name)
            output = status.execute()

            if (output.returncode == 0):
                d = json.loads(output.stdout)

                vdevs = d.get("pools", {}).get(this.pool_name, {}).get("vdevs", {}).get(this.pool_name, {}).get("vdevs", {})

                if (len(vdevs) == 1):
                    # check if raidz is enabled
                    value = list(vdevs.keys())[0]

                    if (vdevs[value]['vdev_type'] == 'raidz'):
                        cmd = ZPoolAttach(this.pool_name, vdevs[value]['name'],new_device)

            if (cmd is None):
                raise ErrorMessage.get_error(ErrorMessage.E_POOL_ATTACH(new_device))

        else:
            cmd = ZPoolAdd(this.pool_name,new_device)

        trans = RemoteCommandLineTransaction(socket.AF_UNIX,
                                             socket.SOCK_STREAM,
                                             SOCK_PATH, cmd)

        output = trans.run()

        if (not trans.success):
            raise ErrorMessage.get_error(ErrorMessage.E_POOL_ATTACH(output[0]['stderr']))

        this.cfg["pool"]["disks"].append(new_disk_obj.serialise())
        this.flush_config()

    def get_pool_status_id(this) -> Optional[str]:
        if (this.is_pool_configured()):
            pool = this.pool_name
            trans = LocalCommandLineTransaction(ZPoolStatus(pool))
            output = trans.run()
            if (trans.success) and (len(output) > 0):
                output = output[0].get("stdout",{})
                d = json.loads(output)

                root = d.get("pools", {}).get(pool,{})
                return root.get("msgid",None)


    def recover(this) -> None:
        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH, ZPoolClear(this.pool_name,True)
        )

        output = trans.run()

        if (not trans.success):
            raise Exception( ErrorMessage.get_error(ErrorMessage.E_POOL_RECOVERY, output[0]['stderr']))


    def replace(this, old_dev:str, new_dev:Optional[str]=None) -> None:
        trans = RemoteCommandLineTransaction(socket.AF_UNIX,
                                             socket.SOCK_STREAM,
                                             SOCK_PATH, ZPoolReplace(this.pool_name,old_dev,new_dev))

        output = trans.run()

        if (not trans.success):
            raise Exception(f"Unable to replace disk: {output[0]['stderr']}")


    def deconfigure_pool(this) -> None:
        this.cfg['pool'] = {
            "name": None,
            "encrypted": None,
            "redundancy": False,
            "compressed": False,
            "disks": [],
            "tools": {
                "scrub": {
                    "ongoing": False,
                    "last": None
                },
            }
        }

        this.cfg["dataset"] = None

        this.flush_config()
