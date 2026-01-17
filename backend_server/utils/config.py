import json
import os
from backend_server.utils.logger import Logger
from typing import Optional

class NMSConfig(Logger):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(NMSConfig, cls).__new__(cls)
        return cls.instance

    def __init__(this, config_file:str='nms.json'):
        this._config_file = config_file
        this._cfg = {}
        this._tmp_secret = None

        try:
            this.load_configuration_file()
        except FileNotFoundError:
            this.create_default_configuration_file()

    @property
    def config_filename(this) -> str:
        return this._config_file

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
        return this._cfg['access'].get("otp_secret",None)

    def save_otp_secret(this) -> None:
        this._cfg['access']["otp_secret"] = this.temporary_otp_secret
        this.temporary_otp_secret = None
        this.flush_config()

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

        #TODO: call init_pool

        this.flush_config()

    def flush_config(this) -> None:
        this.info(f"Flushing configuration file `{this.config_filename}`")
        try:
            with open(this.config_filename,"w") as h:
                json.dump(this._cfg,h,indent=4)
                this.info(f"Configuration file `{this.config_filename}` flushed correctly")
        except Exception as e:
            this.error(f"Unable to flush the configuration file `{this.config_filename}`: {str(e)}")

