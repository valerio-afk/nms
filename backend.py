import os
import hashlib
import json
import subprocess
import psutil
import socket
import platform
import datetime

from cmdl import CreateKey, ZPoolCreate, ZPoolLabelClear, ZFSCreate, CommandLineTransaction
from constants import KEYPATH, POOLNAME, DATASETNAME
from daemon import NetIOCounter
from celery import Celery, Task
from sqlalchemy.util import OrderedDict
from disk import Disk,DiskStatus
from iface import NetworkInterface
from enum import Enum

hash_password = lambda pwd : hashlib.sha1(pwd.encode()).hexdigest()

__version__ = "0.1dev"

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

class NMSBackend:

    def __init__(this,config_file="nms.json"):
        this._config_file = config_file
        this._cfg = {}
        this._celery_tasks = []
        this._daemons = {'net_counters':NetIOCounter()}

        try:
            this.load_configuration_file()
        except FileNotFoundError as e:
            this.create_default_config_file()

        for daemon in this._daemons.values():
            daemon.start()

    @property
    def config_filename(this):
        return this._config_file

    def append_task(this,task):
        this._celery_tasks.append(task)

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

    def get_tasks_by_path(this,path, pop=False):
        path = path.lower()
        return [ t.task_id for t in this._celery_tasks if (not t.completed ) and path.startswith(t.page.lower()) ]

    def pop_completed_tasks(this, path):
        path = path.lower()
        tasks = [t for t in this._celery_tasks if t.completed and path.startswith(t.page.lower())]

        for t in tasks:
            this._celery_tasks.remove(t)

        return [t for t in tasks]

    def load_configuration_file(this):
        if os.path.exists(this.config_filename):
            with open(this.config_filename, "r") as h:
                this._cfg = json.load(h)
        else:
            raise FileNotFoundError(f"Configuration file {this.config_filename} does not exist")

    def get_disks(this):
        pool_disks = this._cfg['pool'].get("disks",[])
        lsblk_output = subprocess.run(["lsblk", "-J", "-b", "-o", "NAME,MODEL,SERIAL,TYPE,TRAN,SIZE,PATH"],stdout=subprocess.PIPE,text=True)
        lsblk_disks = json.loads(lsblk_output.stdout)

        sata_disks = [x for x in lsblk_disks['blockdevices'] if x['tran'] == 'sata']

        detected_disks = []
        for d in sata_disks:
            status = DiskStatus.NEW

            if (d['path'] in pool_disks):
                status=DiskStatus.ONLINE

            disk = Disk(name=d['name'],
                        model=d['model'],
                        serial=d['serial'],
                        size=d['size'],
                        path=d['path'],
                        status=status
                        )
            detected_disks.append(disk)

        detected_disks.sort(key=lambda x : x.name)

        return detected_disks

    def get_pool_options(this):
        return [
            ("Redundancy", this._cfg['pool'].get("redundancy",False)),
            ("Encryption", False if this._cfg['pool'].get("encrypted", None) is None else True),
            ("Compression", this._cfg['pool'].get("compressed", False)),
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
                network_name = subprocess.check_output(["iwgetid", interface, "--raw"], encoding='utf-8').strip()
            except subprocess.CalledProcessError:
                pass

            iface = NetworkInterface(name=interface, status=is_up, ipv4=ipv4, ipv6=ipv6,network_name=network_name)

            ifaces.append(iface)

        ifaces.sort(key=lambda x:x.name)

        return ifaces

    def get_access_services(this):
        services = this._cfg['access'].get('services',{})

        return sorted([(name.upper(),enabled) for name,enabled in services.items()],key=lambda x:x[0])

    def create_pool(this,redundancy:bool, encryption:bool, compression:bool):

        if this.is_pool_configured():
            raise Exception("The disk array is already configured.")

        disks = [d.path for d in this.get_disks() if d.status == DiskStatus.NEW]

        if redundancy and (len(disks)<3):
            raise Exception("You must have at least 3 disks connected to opt in redundancy.")


        commands = []
        enc_key = None
        if encryption:
            enc_key = KEYPATH
            keygen = CreateKey(enc_key)
            commands.append(keygen)

        poolname = POOLNAME
        datasetname = DATASETNAME

        commands.append(ZPoolLabelClear(disks))
        commands.append(ZPoolCreate(disks,redundancy,enc_key,compression,poolname))
        commands.append(ZFSCreate(poolname,datasetname))

        trans = CommandLineTransaction(*commands)
        output = trans.execute()

        if (not trans.success):
            if (len(output)==0):
                raise Exception("Unknown error")
            else:
                raise Exception(output[-1].stdout)

        this._cfg['pool']['name'] = poolname
        this._cfg['dataset'] = datasetname

        if (redundancy):
            this._cfg['pool']['redundancy'] = True

        if (encryption):
            this._cfg['pool']['encrypted'] = enc_key

        if (compression):
            this._cfg['pool']['compressed'] = True

        this._cfg['pool']['disks'] = disks

        this.flush_config()




    def create_default_config_file(this):
        cfg = {
            "pool" : {
                "name": None,
                "encrypted": None,
                "redundancy": False,
                "compressed": False,
                "disks": {}
            },
            "dataset": None,
            "access":
                {
                    "login":
                        {
                            "username": "afk",
                            "password": hash_password("admin"),
                        },
                    "services":
                        {
                            "sftp": False,
                            "ssh": False,
                            "nfs": False,
                            "smb": False,
                            "web": False,
                        }
                }
        }

        this._cfg = cfg

        this.flush_config()

    def flush_config(this):
        with open(this.config_filename,"w") as h:
            json.dump(this._cfg,h,indent=4)

def celery_init_app(app):
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app


BACKEND = NMSBackend()