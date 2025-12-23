import os
import pyotp
import hashlib
import json
import subprocess
import grp
import re
from importlib import import_module
import psutil
import socket
import platform
import datetime
import base64
from inotify_simple import INotify, flags

from collections import OrderedDict
from celery.result import AsyncResult
from cmdl import CreateKey, ZPoolCreate, ZFSCreate, RemoteCommandLineTransaction, ZpoolScrub, Reboot, \
    Shutdown, JournalCtl, SystemCtlRestart, ZpoolList, ZpoolStatus, ZFSGet, ZFSList, LSBLK, ZFSLoadKey, ZFSMount, \
    ZFSUnLoadKey, ZFSUnmount, UserModChangeHomeDir, APTGetUpdate, APTGetUpgrade, Chown, ZFSDestroy, ZPoolLabelClear, \
    ZPoolImport, ZPoolExport, Wipefs, ZPoolDestroy, ZPoolAdd, ZPoolAttach
from constants import KEYPATH
from flask_daemons import NetIOCounter, ScrubStateChecker, CheckConfigFile
from disk import Disk,DiskStatus
from iface import NetworkInterface
from enum import Enum
from flask import flash
from nms_utils import setup_logger, ansi_to_html
from constants import SOCK_PATH, APT_LISTS
from typing import List,Tuple, Optional
from datetime import timedelta
import pwd


hash_password = lambda pwd : hashlib.sha1(pwd.encode()).hexdigest()

__version__ = "0.1dev"

def scrub_finished_hook():
    flash("Disk array verification completed","success")


class NMSTask:

    def __init__(this, task_id:str,
                       page:Optional[str]=None,
                       action:Optional[str]=None,
                       tag:Optional[str]=None):
        this._task_id = task_id
        this._page = page
        this._action = action
        this._tag = tag

    @property
    def action(this) -> Optional[str]:
        return this._action

    @property
    def tag(this) -> Optional[str]:
        return this._tag

    @property
    def page(this) -> Optional[str]:
        return this._page

    @property
    def task_id(this) -> str:
        return this._task_id

    @property
    def completed(this) -> bool:
        return AsyncResult(this.task_id).ready()

    @property
    def successful(this) -> bool:
        return AsyncResult(this.task_id).successful()

    @property
    def failed(this) -> bool:
        return AsyncResult(this.task_id).failed()

    @property
    def result(this) -> AsyncResult:
        return AsyncResult(this.task_id).result


class LogFilter(Enum):
    FLASK = 0
    BACKEND = 1
    CELERY = 2
    SUDODAEMON = 3

def get_cpu_name():
    with open("/proc/cpuinfo") as f:
        for line in f:
            if "model name" in line:
                return line.split(": ")[1].strip()
    return "Unknown CPU"

class TaskStatus(Enum):
    PROGRESS=0
    SUCCESSFUL=1
    FAILED=-1


class OwnershipHandler():
    def __init__(this,uid,gid):
        this._uid = uid
        this._gid = gid

        super().__init__()

class NMSBackend:#(FileSystemEventHandler):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(NMSBackend, cls).__new__(cls)
        return cls.instance

    def __init__(this,config_file="nms.json"):
        this._config_file = config_file
        this._cfg = {}
        this._celery_tasks = []
        this._daemons = {
            'net_counters':NetIOCounter(),
            'scrub_checker':None,
            'inotify': CheckConfigFile(config_file,this.load_configuration_file),
        }
        this._logger = setup_logger("NMS BACKEND")
        this._watchdog = None

        try:
            this.load_configuration_file()
        except FileNotFoundError as e:
            this.create_default_config_file()



        this._access_services={}

        this._setup_access_services()
        # this._start_tank_observer()

        for daemon in this._daemons.values():
            if (daemon is not None):
                daemon.start()

        if (this.is_pool_configured() and (not this.is_mounted)):
            try:
                this.mount()
            except:
                ...

    def _setup_access_services(this):
        module = import_module("services")
        account = this._cfg.get("access",{}).get("account",{})


        for service,args in this._cfg.get("access",{}).get("services",{}).items():
            try:
                cls = getattr(module,f"{service.upper()}Service")
                arguments = args.copy()
                arguments.update(account)
                arguments['mountpoint'] = this.mountpoint
                this._access_services[service] = cls(**arguments)
            except AttributeError:
                ... #service not implemented yet

        this._access_services['ssh'].add_change_hook("username", this._sys_username_changed)
        this._access_services['ftp'].add_pre_start_hook(this._set_pwd)
        this._access_services['web'].add_change_hook("port", this._web_port_changed)
        this._access_services['web'].add_change_hook("credential", this._web_credentials_changed)
        this._access_services['web'].add_change_hook("authentication", this._web_authentication_changed)

    def _web_port_changed(this,service):
        d = this._cfg.get("access",{}).get("services",{}).get("web",{})
        d['port'] = service.get("port")
        this._cfg['access']['services']['web'] = d

        this.flush_config()

    def _web_credentials_changed(this,service):
        d = this._cfg.get("access",{}).get("services",{}).get("web",{})
        d['credential'] = service.get("credential")
        this._cfg['access']['services']['web'] = d

        this.flush_config()

    def _web_authentication_changed(this,service):
        d = this._cfg.get("access",{}).get("services",{}).get("web",{})
        d['authentication'] = service.get("authentication")
        this._cfg['access']['services']['web'] = d

        this.flush_config()


    def _set_pwd(this, *args, **kwargs):
        if (this.is_pool_configured()):
            mp = this.mountpoint
            username = this._cfg.get("access",{}).get("services").get("account",{}).get("username",None)

            if (username is not None):
                current_pwd = pwd.getpwnam(username).pw_dir

                if (current_pwd!=mp):
                    cmd = UserModChangeHomeDir(username,current_pwd,mp)

                    trans = RemoteCommandLineTransaction(
                        socket.AF_UNIX,
                        socket.SOCK_STREAM,
                        SOCK_PATH,
                        cmd
                    )
                    trans.run()


    def _sys_username_changed(this,service):
        old_username = this._cfg['access']['account']['username']
        new_username = service.get("username")
        this._cfg['access']['account']['username'] = new_username
        this.flush_config()

        smb = this._access_services.get("smb",None)
        smb.set("username",new_username)


        if ((smb is not None) and (smb.is_active)):
            smb.disable(old_username)

    @property
    def config_filename(this):
        return this._config_file

    @property
    def logger(this):
        return this._logger

    def append_task(this,task):
        this._celery_tasks.append(task)

    @property
    def is_otp_configured(this):
        return this._cfg['access'].get("otp_secret",None) is not None

    def set_otp_secret(this,secret):
        this._cfg['access']['otp_secret'] = secret
        this.flush_config()

    def verify_otp(this,otp):
        secret = this._cfg['access'].get('otp_secret',None)

        if (secret is not None):
            totp = pyotp.TOTP(secret)
            return totp.verify(otp)

        return False

    @property
    def get_tasks(this) -> List[NMSTask]:
        return [t for t in this._celery_tasks]


    @property
    def blocked_pages(this):
        return [ t.page for t in this._celery_tasks if (not t.completed ) and (t.page is not None)]

    @property
    def get_net_counters(this):
        net_io = this._daemons['net_counters']
        return {"received": net_io.bytes_received, "sent": net_io.bytes_sent}

    @property
    def system_information(this):
        sys_info = OrderedDict()

        #uptime
        boot_ts = psutil.boot_time()  # epoch seconds when system booted
        boot_dt = datetime.datetime.fromtimestamp(boot_ts)

        sys_info['Uptime'] = f"Since {boot_dt.strftime("%A, %d %B %Y at %H:%M")}"

        #NMS version

        sys_info['NMS Version'] = __version__
        #CPU

        sys_info['CPU'] = f"{get_cpu_name()} with {psutil.cpu_count(logical=True)} core(s)"
        #OS

        sys_info['OS'] = " ".join([platform.system(), platform.release(), platform.version(), platform.machine()])

        # cpu load

        sys_info['_cpu_load'] = psutil.cpu_percent(interval=1)
        # memory load

        sys_info['_memory_load'] = psutil.virtual_memory().percent

        #net_conunters
        sys_info['_net_counters'] = this.get_net_counters

        return sys_info

    def get_tasks_by_path(this,path):
        path = path.lower()
        return [ t for t in this._celery_tasks if (not t.completed ) and path.startswith(t.page.lower()) ]

    def pop_completed_tasks(this, path=None):
        tasks = [t for t in this._celery_tasks if t.completed and ( (path is None) or path.lower().startswith(t.page.lower()))]

        for t in tasks:
            this._celery_tasks.remove(t)

        return [t for t in tasks]

    def load_configuration_file(this):
        this._logger.info(f"Loading configuration file `{this.config_filename}`")
        if os.path.exists(this.config_filename):
            with open(this.config_filename, "r") as h:
                this._cfg = json.load(h)
                this._logger.info(f"Configuration file `{this.config_filename}` loaded successfully")
        else:
            this._logger.error(f"Configuration file `{this.config_filename}` not found")
            raise FileNotFoundError(f"Configuration file {this.config_filename} does not exist")


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


        # detected_disks = []
        # for d in sata_disks:
        #     status = DiskStatus.NEW
        #
        #     for disk_in_pool in pool_disks:
        #         if (disk_in_pool['model'] == d['model']) and (disk_in_pool['serial'] == d['serial']):
        #             status=DiskStatus.ONLINE
        #             break
        #
        #     disk = Disk(name=d['name'],
        #                 model=d['model'],
        #                 serial=d['serial'],
        #                 size=d['size'],
        #                 path=d['path'],
        #                 status=status
        #                 )
        #     detected_disks.append(disk)

        detected_disks.sort(key=lambda x : x.path)


        return detected_disks

    @property
    def pool_name(this):
        return this._cfg['pool'].get("name", None)

    @property
    def dataset_name(this):
        return this._cfg.get("dataset", None)

    @property
    def get_pool_capacity(this):
        if (not this.is_pool_configured()):
            return None

        zpool_list = ZpoolList(this.pool_name)

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
    def has_redundancy(this):
        return this._cfg['pool'].get("redundancy",False)

    @property
    def has_encryption(this):
        return False if this._cfg['pool'].get("encrypted", None) is None else True

    @property
    def key_filename(this):
        return this._cfg['pool'].get("encrypted", None)

    @property
    def has_compression(this):
        return this._cfg['pool'].get("compressed", False)

    @property
    def get_scrub_info(this):
        return {k: v for k, v in this._cfg['pool'].get('tools', {}).get('scrub', {}).items()}

    def get_pool_options(this):
        return [
            ("Redundancy", this.has_redundancy),
            ("Encryption", this.has_encryption),
            ("Compression", this.has_compression),
        ]

    def is_pool_configured(this):
        return True if this._cfg['pool'].get("name",None) is not None else False

    def iface_status(this):

        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        ifaces = []

        for interface, addr_list in addrs.items():
            is_up = stats[interface].isup if interface in stats else False
            ipv4 = None
            ipv6 = None

            for addr in addr_list:
                if addr.family == socket.AF_INET:
                    ipv4 = addr.address
                elif addr.family == socket.AF_INET6:
                    ipv6 = addr.address

            network_name = None

            try:
                nmcli = ["nmcli", "-t", "-f", "GENERAL.CONNECTION", "device", "show", interface]
                nmcli_output = subprocess.check_output(nmcli, encoding='utf-8').strip().split(":")

                if (len(nmcli_output)==2):
                    network_name = nmcli_output[1].strip()

            except subprocess.CalledProcessError:
                pass

            iface = NetworkInterface(name=interface, status=is_up, ipv4=ipv4, ipv6=ipv6,network_name=network_name)

            ifaces.append(iface)

        ifaces.sort(key=lambda x:x.name)

        return ifaces

    @property
    def mountpoint(this):
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
                return d.get('datasets', {}).get(f"{tank}/{dataset}", {}).get("properties", {}).get("mountpoint",{}).get("value",None)
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

        if (len(output)==1):
            d = json.loads(output[0].get("stdout",{}))
            tank = this.pool_name
            dataset = this.dataset_name

            if ((tank is not None) and (dataset is not None)):
                mounted = d.get('datasets',{}).get(f"{tank}/{dataset}",{}).get("properties",{}).get("mounted",{}).get("value","no")
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

    def detach(this):
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

    def unmount(this):
        if (not this.is_pool_configured()):
            raise Exception("Disk array not configured")

        this.disable_all_access_services()

        cmds = [
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

    @property
    def get_updates(this):
        return [pkg for pkg in this._cfg.get("updates",{}).get("apt",[])]

    @property
    def get_access_services(this):
        return  this._access_services

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
            ZFSDestroy(tank,dataset),
            ZFSCreate(tank,dataset)
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

    def disable_all_access_services(this):
        for name, s in this._access_services.items():
            if s.is_active:
                try:
                    s.disable()
                except:
                    raise Exception(f"Unable to disable {name.upper()} service. Please disable it manually.")


    def destroy_tank(this):
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

        this._cfg['pool']= {
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

        this._cfg["dataset"] = None

        this.flush_config()

        this.rm_mountpoint(mountpoint)

    def rm_mountpoint(this,mountpoint):
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




    def get_importable_pools(this):

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
            raise Exception("The disk array is already configured.")

        disks_objs = [d for d in this.get_disks() if d.status == DiskStatus.NEW]

        if redundancy and (len(disks)<3):
            raise Exception("You must have at least 3 disks connected to opt in redundancy.")

        for disk in disks:
            trans = RemoteCommandLineTransaction(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
                SOCK_PATH,
                ZPoolLabelClear(disk),
            )

            trans.run()

            if (not trans.success):
                RemoteCommandLineTransaction(
                    socket.AF_UNIX,
                    socket.SOCK_STREAM,
                    SOCK_PATH,
                    Wipefs(disk),
                ).run()



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
                raise Exception("Unknown error")
            else:
                raise Exception(output[-1].get('stderr',None))

        this._cfg['pool']['name'] = poolname
        this._cfg['dataset'] = datasetname

        if (redundancy):
            this._cfg['pool']['redundancy'] = True

        if (encryption):
            this._cfg['pool']['encrypted'] = enc_key

        if (compression):
            this._cfg['pool']['compressed'] = True

        this._cfg['pool']['disks'] = []

        this._cfg['pool']['disks'] = [d.serialise() for d in disks_objs if d.has_any_paths(disks)]

        this.flush_config()

        this.change_permissions()
        # this._start_tank_observer()

    def change_permissions(this):
        if (this.is_mounted):
            message = {
                "action": "ch_tank_perm",
                "args": {"pool": this.pool_name,"dataset":this.dataset_name,"group":"users"}
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


    def get_tank_key(this):
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

    def import_tank_key(this, handle):

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


    def import_pool(this,poolname,load_key=False):
        command = [ZPoolImport(poolname)]

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
            this.mount()
        except Exception as e:
            RemoteCommandLineTransaction(socket.AF_UNIX,
                                         socket.SOCK_STREAM,
                                         SOCK_PATH, ZPoolExport(poolname)).run()

            this.load_configuration_file() #revert to previous state

            raise Exception(str(e))


        this.flush_config()


    def reboot(this):

        this._logger.info("Rebooting...")

        try:
            trans = RemoteCommandLineTransaction(socket.AF_UNIX,
                                                 socket.SOCK_STREAM,
                                                 SOCK_PATH, Reboot())

            trans.run()
        except Exception as e:
            this._logger.error(f"Unable to reboot the system: {e}")

    def shutdown(this):
        this._logger.info("Shutting down...")

        try:
            trans = RemoteCommandLineTransaction(socket.AF_UNIX,
                                                 socket.SOCK_STREAM,
                                                 SOCK_PATH, Shutdown())

            trans.run()
        except Exception as e:
            this._logger.error(f"Unable to shut down the system: {e}")

    def start_scrub(this):
        pool = this.pool_name

        if (pool is None):
            raise Exception("No disk array found")

        command = ZpoolScrub(pool)
        trans = RemoteCommandLineTransaction(socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,command)

        output = trans.run()

        if (len(output)!=1):
            raise Exception("Unknown Error")

        if (output[0]['returncode']!=0):
            raise Exception (output[0]['stderr'])

        this._cfg['pool']['tools']['scrub']['ongoing'] = True
        this._cfg['pool']['tools']['scrub']['last'] = datetime.datetime.now().timestamp()

        this.flush_config()

    def get_last_scrub_report(this):
        output = ZpoolStatus(this.pool_name).execute()


        if (output.returncode == 0):
            d = json.loads(output.stdout)
            scan_stats = d.get('pools', {}).get(this.pool_name, {}).get('scan_stats', {})

            if (scan_stats.get('function', "") == "SCRUB"):
                started = int(scan_stats.get('start_time', -1))
                ended = int(scan_stats.get('end_time', -1))
                errors = scan_stats.get('errors', "-")

                started = datetime.datetime.fromtimestamp(started).strftime("%c") if started >=0 else "-"
                ended = datetime.datetime.fromtimestamp(ended).strftime("%c") if ended >= 0 else "-"

                return {
                    'Started at': started,
                    'Ended at': ended,
                    "Errors": errors
                }

        return None




    def create_default_config_file(this):
        this._logger.info(f"Creating default configuration file")
        cfg = {
            "pool" : {
                "name": None,
                "encrypted": None,
                "redundancy": False,
                "compressed": False,
                "disks": [],
                "tools": {
                    "scrub": {
                        "ongoing" : False,
                        "last" : None
                    },
                }
            },
            "dataset": None,
            "access": {
                "account" : {
                  "otp_secret": None,
                  "username": "tuttoweb",
                  "group": "users"
                },
                "services":
                    {
                        "ssh": {
                            "service_name": "ssh.service",
                        },
                        "ftp": {
                            "service_name": "vsftpd.service"
                        },
                        "nfs": {"service_name":["rpcbind.service","nfs-server.service"]},
                        "smb": {"service_name":["smbd.service","nmbd.service"]},
                        "web": {
                            "service_name": "ifm-server",
                            "port":8080,
                            "authentication": False,
                            "credential": "afk:$2y$10$WSpWpteVT3wt6oDPSZlmnOTT9g3/tcKmpWED26IFlHNx/27B/I.Wq"
                        },
                    }
            },
            "updates":{
                "apt" : []
            },
            "systemd": {
                "services": ['nmswebapp.service','celeryworker.service','sudodaemon.service']
            }
        }

        this._cfg = cfg

        this.init_pool()

        this.flush_config()

    def init_pool(this):

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


        status = ZpoolStatus(pool_name)
        output = status.execute()

        if (output.returncode==0):
            d = json.loads(output.stdout)

            vdevs = d.get("pools",{}).get(pool_name,{}).get("vdevs",{}).get(pool_name,{}).get("vdevs",{})

            if (len(vdevs)==1):
                # check if raidz is enabled
                value = list(vdevs.keys())[0]

                if (vdevs[value]['vdev_type']=='raidz'):
                    this._cfg['pool']['redundancy'] = True
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

                this._cfg['pool']['disks'] = [d.serialise() for d in disks_in_pool]


                this._cfg['pool']['name'] = pool_name
                this._cfg['dataset'] = dataset_name

                pool_properties = ZFSGet(pool_name)
                prop_output = pool_properties.execute()

                if (prop_output.returncode == 0):
                    d_prop = json.loads(prop_output.stdout)
                    pool_properties = d_prop.get('datasets',{}).get(pool_name,{}).get("properties",{})
                    if (len(pool_properties) > 0):
                        # check compression
                        this._cfg['pool']['compressed'] = True if (pool_properties['compression']['value'].lower() != "off") else False
                        # check for encryption
                        enc_enabled = pool_properties['encryption']['value'].lower() != "off"

                        if (enc_enabled):
                            key_location = pool_properties['keylocation']['value']
                            if key_location.startswith("file://"):
                                key_location = key_location[len("file://"):]

                            this._cfg['pool']['encrypted'] = key_location


    def expand_pool(this,new_device:str) -> None:
        cmd = None

        disks = this.get_attachable_disks

        new_disk_obj = [ d for d in disks if d.has_path(new_device)]

        if (len(new_disk_obj)!=1):
            raise Exception(f"Could not retrieve information for the disk: {new_device}")

        new_disk_obj = new_disk_obj.pop()

        this.disable_all_access_services()
        this.unmount()

        if this.has_redundancy:
            status = ZpoolStatus(this.pool_name)
            output = status.execute()

            if (output.returncode == 0):
                d = json.loads(output.stdout)

                vdevs = d.get("pools", {}).get(this.pool_name, {}).get("vdevs", {}).get(this.pool_name, {}).get("vdevs", {})

                if (len(vdevs) == 1):
                    # check if raidz is enabled
                    value = list(vdevs.keys())[0]

                    if (vdevs[value]['vdev_type'] == 'raidz'):
                        cmd = ZPoolAttach(this.pool_name, vdevs[value]['name'],new_device)

            assert(cmd is not None,"Unable to attach new device to disk array.")

        else:
            cmd = ZPoolAdd(this.pool_name,new_device)

        trans = RemoteCommandLineTransaction(socket.AF_UNIX,
                                             socket.SOCK_STREAM,
                                             SOCK_PATH, cmd)

        output = trans.run()

        if (not trans.success):
            raise Exception(f"Unable to attach new device to disk array: {output[0]['stderr']}")

        this._cfg["pool"]["disks"].append(new_disk_obj.serialise())
        this.flush_config()

    @property
    def get_array_expansion_status(this) -> Tuple[Optional[float], Optional[timedelta], bool]:

        if (not this.is_pool_configured()):
            raise Exception(f"Disk array not configured yet.")

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            ZpoolStatus(this.pool_name)
        )

        output = trans.run()


        if (not trans.success):
            raise Exception(f"Unable to get array expansion status: {output[0]['stderr']}")

        zpool_output = output[0]['stdout']

        in_progress = re.search(
            r'([\d.]+)%\s+done,\s+([\d:]+)\s+to\s+go',
            zpool_output
        )

        if in_progress:
            percent = float(in_progress.group(1))
            h, m, s = map(int, in_progress.group(2).split(":"))
            return percent, timedelta(hours=h, minutes=m, seconds=s), False

        completed = re.search(r'expand:\s+expanded', zpool_output)
        if completed:
            return 100.0, timedelta(0), True

        return None, None, False

    @property
    def get_attachable_disks(this) -> List[Disk]:



        disks = [d for d in this.get_disks() if d.status == DiskStatus.NEW]
        config_disk = this.get_pool_disks()

        physical_paths = []

        for d in config_disk:
            physical_paths.extend(d.physical_paths)

        physical_paths = set(physical_paths)
        attachable_disks = []

        # raise Exception([disks,config_disk])

        for d in disks:

            if (len(physical_paths.intersection(set(d.physical_paths)))==0):
                attachable_disks.append(d)

#         raise Exception(attachable_disks)

        return attachable_disks







    def flush_config(this):
        this._logger.info(f"Flushing configuration file `{this.config_filename}`")
        try:
            with open(this.config_filename,"w") as h:
                json.dump(this._cfg,h,indent=4)
                this._logger.info(f"Configuration file `{this.config_filename}` flushed correctly")
        except Exception as e:
            this._logger.error(f"Unable to flush the configuration file `{this.config_filename}`: {str(e)}")

    def get_logs(this, what=LogFilter.FLASK):
        grep = None
        service = "nmswebapp.service"
        match (what):
            case LogFilter.CELERY:
                service = "celeryworker.service"
            case LogFilter.SUDODAEMON:
                service = "sudodaemon.service"
            case LogFilter.BACKEND:
                grep = 'NMS BACKEND'

        journalctl = JournalCtl(service,grep)

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            journalctl
        )
        output = trans.run()

        if (len(output)==1):
            return ansi_to_html(output[0]['stdout'])
        else:
            return None


    def restart_systemd_services(this):
        cmds = [ SystemCtlRestart(service) for service in this._cfg['systemd'].get('services',[]) ]

        if (len(cmds)>0):
            trans = RemoteCommandLineTransaction(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
                SOCK_PATH,
                *cmds
            )

            trans.run()

    def check_scrub_status(this):
        if (this._cfg['pool']['tools']['scrub']['ongoing'] == True):
            daemon = this._daemons['scrub_checker']

            if (daemon is not None):
                if (not daemon.is_running):
                    this._cfg['pool']['tools']['scrub']['ongoing'] = False
                    this.flush_config()
                    this._daemons['scrub_checker'] = None
                    this._logger.info(f"Scrub checker thread terminated {daemon.completion_handler}")
                    scrub_finished_hook()
            else:
                daemon = ScrubStateChecker(this.pool_name)
                this._daemons['scrub_checker'] = daemon
                daemon.start()
                this._logger.info("Scrub checker thread started")

    def get_apt_updates(this):
        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            APTGetUpdate()
        )

        output = trans.run()


        try:
            if (trans.success):
                trans = RemoteCommandLineTransaction(
                    socket.AF_UNIX,
                    socket.SOCK_STREAM,
                    SOCK_PATH,
                    APTGetUpgrade(dry_run=True)
                )

                output = trans.run()

                if (trans.success):
                    stdout = output[0].get("stdout","")

                    updates = []

                    for line in stdout.splitlines():
                        if (line.startswith("Inst ")):
                            pkg = line.split()

                            if (len(pkg)>=2):
                                updates.append(pkg[1])

                    this._cfg['updates']['apt'] = updates
                    this.flush_config()

                else:
                    raise Exception(output[0]['stdout'])
            else:
                raise Exception(output[0]['stdout'])
        except Exception as e:
            raise Exception(f"Could not get list of updates: {str(e)}")

    def get_apt_upgrade(this):
        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            APTGetUpdate()
        )

        output = trans.run()


        try:
            if (trans.success):
                trans = RemoteCommandLineTransaction(
                    socket.AF_UNIX,
                    socket.SOCK_STREAM,
                    SOCK_PATH,
                    APTGetUpgrade(dry_run=False)
                )

                output = trans.run()

                if (trans.success):
                    this._cfg['updates']['apt'] = []
                    this.flush_config()

                else:
                    raise Exception(output[0]['stdout'])
            else:
                raise Exception(output[0]['stdout'])
        except Exception as e:
            raise Exception(f"Could not install system updates: {str(e)}")

    def last_apt_time(this):
        times = []
        for fname in os.listdir(APT_LISTS):
            path = os.path.join(APT_LISTS, fname)
            if os.path.isfile(path):
                times.append(os.path.getmtime(path))

        if times:
            return datetime.datetime.fromtimestamp(max(times))
        return None

    def change_ownership(this, path):
        account = this._cfg.get("access", {}).get("account", {})

        try:
            uid = pwd.getpwnam(account.get("username","")).pw_uid
            gid = grp.getgrnam(account.get("group","")).gr_gid

            trans = RemoteCommandLineTransaction(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
                SOCK_PATH,
                Chown(uid,gid,path,True)
            )

            output = trans.run()

            if (trans.success):
                this._logger.info(f"Changed ownership: {path}")
            else:
                this._logger.error(f"Error while changing ownership: {output['stderr']}")

        except Exception as e:
            this._logger.error(f"Error while changing ownership: {str(e)}")




    # def on_created(this, event):
    #     this.change_ownership(event.src_path)
    #
    # def on_modified(this, event):
    #     this.change_ownership(event.src_path)
    #
    # def _start_tank_observer(this):
    #     path = this.mountpoint
    #
    #     if ((this._watchdog is None) and (path is not None)):
    #         this._watchdog = Observer()
    #         this._watchdog.schedule(this,path,recursive=True)
    #         this._watchdog.start()
    #         this._logger.info("Tank Directory Observer started")



