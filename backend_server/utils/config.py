import json
import os
from nms_shared.enums import DiskStatus
from backend_server.utils.responses import Disk
from backend_server.utils.cmdl import ZFSList, ZPoolStatus, LSBLK, ZFSGet
from backend_server.utils.daemons import NetIOCounter
from backend_server.utils.logger import Logger
from backend_server.utils.cmdl import ZPoolList
from fastapi import HTTPException
from typing import Optional, Dict, List

from backend_server.utils.responses import ErrorMessage
from nms_shared import ErrorMessages


class NMSConfig(Logger):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(NMSConfig, cls).__new__(cls)
        return cls.instance

    def __init__(this, config_file:str='nms.json'):
        super().__init__()
        this._config_file = config_file
        this._cfg = {}
        this._tmp_secret = None
        this._daemons = {
            'netcounter': NetIOCounter()
        }

        for d in this._daemons.values():
            d.start()

        try:
            this.load_configuration_file()
        except FileNotFoundError:
            this.create_default_configuration_file()

    #BASE PROPERTIES

    @property
    def config_filename(this) -> str:
        return this._config_file

    # AUTH/OTP PROPERTIES

    @property
    def is_otp_configured(this) -> bool:
        return this.otp_secret is not None

    @property
    def temporary_otp_secret(this) -> Optional[str]:
        return this._tmp_secret

    @temporary_otp_secret.setter
    def temporary_otp_secret(this,value:Optional[str]) -> None:
        this._tmp_secret = value

    @property
    def otp_secret(this) -> Optional[str]:
        return this._cfg['access'].get("otp_secret")

    #NETWORK PROPERTIES

    @property
    def net_counter(this) -> Optional[NetIOCounter]:
        return this._daemons.get("netcounter")

    # POOL PROPERTIES

    @property
    def has_redundancy(this) -> bool:
        return this._cfg.get('pool',{}).get("redundancy", False)

    @property
    def has_encryption(this) -> bool:
        return this._cfg.get('pool',{}).get("encrypted", None) is not None

    @property
    def has_compression(this) -> bool:
        return this._cfg.get('pool',{}).get("compressed", False)

    @property
    def dataset_name(this) -> Optional[str]:
        return this._cfg.get("dataset")

    @property
    def key_filename(this) -> Optional[str]:
        return this._cfg.get('pool').get("encrypted", None)

    @property
    def pool_name(this) -> str:
        return this._cfg.get("pool",{}).get("name")

    @property
    def get_pool_capacity(this) -> Optional[Dict[str, int]]:
        if (not this.is_pool_configured):
            return None

        zpool_list = ZPoolList(this.pool_name)

        output = zpool_list.execute()

        if (output.returncode == 0):
            d = json.loads(output.stdout)

            pool_properties = d.get('pools', {}).get(this.pool_name, {}).get('properties', None)

            if (pool_properties is not None):
                return {
                    "used": int(pool_properties.get('allocated', {}).get('value', 0)),
                    "total": int(pool_properties.get('size', {}).get('value', 0))
                }
            else:
                raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_CAPACITY.name))
        else:
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_CAPACITY.name,params=[output.stderr]))

    @property
    def mountpoint(this) -> Optional[str]:
        cmd = ZFSList(properties=["mountpoint"])
        process = cmd.execute()

        if process.returncode != 0:
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_MOUNTPOINT.name,params=[process.stderr]))

        d = json.loads(process.stdout)
        pool = CONFIG.pool_name
        dataset = CONFIG.dataset_name

        return (d.get("datasets",{})
                .get(f"{pool}/{dataset}",{})
                .get("properties", {})
                .get("mountpoint",{})
                .get("value"))

    @property
    def is_mounted(this) -> bool:
        cmd = ZFSList(properties=["mounted"])
        process = cmd.execute()

        if process.returncode != 0:
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_POOL_MOUNT_STATUS.name,params=[process.stderr]))

        d = json.loads(process.stdout)
        pool = CONFIG.pool_name
        dataset = CONFIG.dataset_name

        return (d.get("datasets", {})
                .get(f"{pool}/{dataset}", {})
                .get("properties", {})
                .get("mounted", {})
                .get("value","no").lower()) != "no"

    @property
    def is_pool_configured(this) -> bool:
        return this._cfg.get('pool',{}).get("name", None) is not None

    @property
    def is_pool_present(this) -> bool:
        if (not this.is_pool_configured):
            return False

        cmd = ZPoolStatus(this.pool_name)
        process = cmd.execute()

        return process.returncode == 0

    # DISK PROPERTIES
    @property
    def configured_disks(this) -> List[Disk]:
        conf_disks = this._cfg.get("pool",{}).get("disks",{})

        disks = []

        for d in conf_disks:
            cfg_disk = Disk(
                name = d["name"],
                model = d["model"],
                serial = d["serial"],
                path = d["path"],
                size = d["size"],
                status=DiskStatus.NEW
            )

            cfg_disk.cached_physical_paths = d["physical_paths"]

            disks.append(cfg_disk)

        return disks

    # ACCESS SERVICES PROPERTIES
    def access_account(this) -> dict:
        return this._cfg.get("access", {}).get("account", {})

    # BASE METHODS

    def load_configuration_file(this) -> None:
        this.info(f"Loading configuration file `{this.config_filename}`")
        if os.path.exists(this.config_filename):
            with open(this.config_filename, "r") as h:
                this._cfg = json.load(h)
                this.info(f"Configuration file `{this.config_filename}` loaded successfully")
        else:
            this.error(f"Configuration file `{this.config_filename}` not found")
            raise FileNotFoundError()

    def create_default_config_file(this) -> None:
        this.info(f"Creating default configuration file")
        cfg = {
            "pool" : {
                "name": None,
                "encrypted": None,
                "redundancy": False,
                "compressed": False,
                # "disks": [],
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

    def flush_config(this) -> None:
        this.info(f"Flushing configuration file `{this.config_filename}`")
        try:
            with open(this.config_filename,"w") as h:
                json.dump(this._cfg,h,indent=4)
                this.info(f"Configuration file `{this.config_filename}` flushed correctly")
        except Exception as e:
            this.error(f"Unable to flush the configuration file `{this.config_filename}`: {str(e)}")

    #AUTH/OTP METHODS

    def save_otp_secret(this) -> None:
        this._cfg['access']["otp_secret"] = this.temporary_otp_secret
        this.temporary_otp_secret = None
        this.flush_config()

    #POOL METHODS
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


    def deinit_pool(this) -> None:
        this._cfg['pool'] = {
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

    def config_pool(this,pool_name:str,dataset_name:str,redundancy:bool,encription_key:Optional[str],compressed:bool,disks:List[Disk]) -> None:
        this._cfg['pool'] = {
            "name": pool_name,
            "encrypted": encription_key,
            "redundancy": redundancy,
            "compressed": compressed,
            "disks": [d.serialise() for d in disks],
            "tools": {
                "scrub": {
                    "ongoing": False,
                    "last": None
                },
            }
        }

        this._cfg["dataset"] = dataset_name






CONFIG = NMSConfig()