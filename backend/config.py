from disk import Disk, DiskStatus
from typing import List
import json
import os

class ConfigMixin:
    def __init__(this,*args,**kwargs):
        config_file = kwargs.pop('config_file',None)

        if (config_file is None):
            if (len(args)>0):
                config_file = args[0]
            else:
                raise Exception("Configuration file not provided")

        this._config_file = config_file
        this._cfg = {}

        try:
            this.load_configuration_file()
        except FileNotFoundError as e:
            this.create_default_config_file()

        super().__init__(*args, **kwargs)

    @property
    def cfg(this) -> dict:
        return this._cfg

    @property
    def config_filename(this) -> str:
        return this._config_file

    def load_configuration_file(this) -> None:
        this.logger.info(f"Loading configuration file `{this.config_filename}`")
        if os.path.exists(this.config_filename):
            with open(this.config_filename, "r") as h:
                this._cfg = json.load(h)
                this.logger.info(f"Configuration file `{this.config_filename}` loaded successfully")
        else:
            this.logger.error(f"Configuration file `{this.config_filename}` not found")
            raise FileNotFoundError(f"Configuration file {this.config_filename} does not exist")

    def create_default_config_file(this) -> None:
        this.logger.info(f"Creating default configuration file")
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
        this.logger.info(f"Flushing configuration file `{this.config_filename}`")
        try:
            with open(this.config_filename,"w") as h:
                json.dump(this._cfg,h,indent=4)
                this.logger.info(f"Configuration file `{this.config_filename}` flushed correctly")
        except Exception as e:
            this.logger.error(f"Unable to flush the configuration file `{this.config_filename}`: {str(e)}")


    def get_configured_disks(this) -> List[Disk]:
        conf_disks = this.cfg.get("pool",{}).get("disks",{})

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
