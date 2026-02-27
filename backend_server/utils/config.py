from backend_server.utils.cmdl import Chown, LocalCommandLineTransaction, Groups, ZPoolList
from backend_server.utils.cmdl import ZFSList, ZPoolStatus, LSBLK, ZFSGet, UserModChangeHomeDir, ZFSGetQuota, Chmod
from backend_server.utils.logger import Logger
from backend_server.utils.responses import ErrorMessage, UserProfile, Quota
from backend_server.utils.services import SystemService
from backend_server.utils.threads import FreeDNS, DNSExit, Dynv6, ClouDNS
from backend_server.utils.threads import NetIOCounter, DDNSNoIP, LongWaitThread, DDNSServiceThread, DuckDNS, DynuDDNS
from cryptography.fernet import Fernet
from fastapi import HTTPException
from importlib import import_module
from nms_shared import ErrorMessages
from nms_shared.disks import Disk
from nms_shared.enums import DiskStatus, UserPermissions
from typing import Optional, Dict, List, Any, Type
import base64
import datetime
import hashlib
import json
import os
import pwd

from nms_shared.utils import match_permissions


def collapse_permissions(user_permissions:List[str], all_permissions:List[str]) -> List[str]:
    def build_nested(perms):
        root = {}
        for perm in perms:
            node = root
            for part in perm.split("."):
                node = node.setdefault(part, {})
        return root

    all_tree = build_nested(all_permissions)
    user_tree = build_nested(user_permissions)

    # special case: user has everything
    if set(user_permissions) == set(all_permissions):
        return ["*"]

    result = []

    def reduce(all_node, user_node, path):

        # if user does not have this branch
        if user_node is None:
            return False

        # leaf node
        if not all_node:
            result.append(".".join(path))
            return True

        all_owned = True

        for key, child in all_node.items():
            owned = reduce(
                child,
                user_node.get(key) if user_node else None,
                path + [key]
            )
            if not owned:
                all_owned = False

        if all_owned:
            prefix = ".".join(path)

            # remove children (collapse)
            result[:] = [
                r for r in result
                if not r.startswith(prefix + ".")
            ]

            result.append(prefix + ".*")
            return True

        return False

    for key, child in all_tree.items():
        reduce(child, user_tree.get(key), [key])

    return sorted(set(result))

class NMSConfig(Logger):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(NMSConfig, cls).__new__(cls)
        return cls.instance

    def __init__(this, config_file:str='nms.json'):
        super().__init__()
        this._config_file = config_file
        this._cfg = {}
        this._tmp_secret = {}
        this._daemons = {
            'netcounter': NetIOCounter()
        }

        for d in this._daemons.values():
            d.start()

        try:
            this.load_configuration_file()
        except FileNotFoundError:
            this.create_default_config_file()

        this._access_services = {}
        this._setup_access_services()
        this._issued_tokens = {}

        this._ddns_init()


    def _setup_access_services(this) -> None:
        module = import_module("backend_server.utils.services")
        # account = this._cfg.get("access",{}).get("account",{})


        for service,args in this._cfg.get("access",{}).get("services",{}).items():
            try:
                cls = getattr(module,f"{service.upper()}Service")
                arguments = args.copy()
                # arguments.update(account)
                arguments['mountpoint'] = this.mountpoint
                this._access_services[service] = cls(**arguments)
            except AttributeError:
                ... #service not implemented yet

        this._access_services['web'].add_change_hook("port", this._web_port_changed)
        this._access_services['web'].add_change_hook("credential", this._web_credentials_changed)
        this._access_services['web'].add_change_hook("authentication", this._web_authentication_changed)

        for admin in this.admins:
            for service in this.access_services.values():
                service.permission_granted(admin.username)


    def _web_port_changed(this, service) -> None:
        d = this._cfg.get("access", {}).get("services", {}).get("web", {})
        d['port'] = service.get("port")
        this._cfg['access']['services']['web'] = d

        this.flush_config()

    def _web_credentials_changed(this, service) -> None:
        d = this._cfg.get("access", {}).get("services", {}).get("web", {})
        d['credential'] = service.get("credential")
        this._cfg['access']['services']['web'] = d

        this.flush_config()

    def _web_authentication_changed(this, service) -> None:
        d = this._cfg.get("access", {}).get("services", {}).get("web", {})
        d['authentication'] = service.get("authentication")
        this._cfg['access']['services']['web'] = d

        this.flush_config()


    def _sys_username_changed(this,service) -> None:
        old_username = this._cfg['access']['account']['username']
        new_username = service.get("username")
        this._cfg['access']['account']['username'] = new_username
        this.flush_config()

        smb = this._access_services.get("smb",None)
        smb.set("username",new_username)


        if ((smb is not None) and (smb.is_active)):
            smb.disable(old_username)

    def _set_pwd(this, *args, **kwargs) -> None:
        if (this.is_pool_configured):
            mp = this.mountpoint
            username = this._cfg.get("access",{}).get("services").get("account",{}).get("username",None)

            if (username is not None):
                current_pwd = pwd.getpwnam(username).pw_dir

                if (current_pwd!=mp):
                    cmd = UserModChangeHomeDir(username,current_pwd,mp)

                    cmd.execute()

    #BASE PROPERTIES

    @property
    def config_filename(this) -> str:
        return this._config_file

    # AUTH/OTP PROPERTIES

    @property
    def is_otp_configured(this) -> bool:
        secrets = this.otp_secrets
        return len(secrets) > 0

    @property
    def temporary_otp_secrets(this) -> Dict[str, str]:
        return {k:v for k,v in this._tmp_secret.items()}

    @property
    def otp_secrets(this) -> Dict[str,str]:
        users = this._cfg.get("users",{})

        return {uname:secret for uname,props in users.items() if (secret:=props.get("otp_secret")) is not None }

    @property
    def issued_tokens(this) -> List[str]:
        now = datetime.datetime.now().timestamp()
        this._issued_tokens = {t:exp for t,exp in this._issued_tokens.items() if exp>now}

        return list(this._issued_tokens.keys())

    #NETWORK PROPERTIES
    @property
    def net_counter(this) -> Optional[NetIOCounter]:
        return this._daemons.get("netcounter")

    @property
    def vpn_service(this) -> Optional[str]:
        for s in this._cfg.get("systemd", {}).get("services", []):
            if s.startswith("wg-quick"):
                return s

        return None

    @property
    def vpn_public_ip(this) -> str:
        return this._cfg.get("vpn",{}).get("endpoint")

    @vpn_public_ip.setter
    def vpn_public_ip(this,endpoint:str) -> None:
        this._cfg["vpn"]['endpoint'] = endpoint

    @property
    def vpn_peer_names(this) -> List[str]:
        return this._cfg.get("vpn",{}).get('peers', [])

    @property
    def ddns_providers(this)->List[Dict[str,Any]]:
        return this._cfg.get('ddns',{})

    def ddns_provider_set_last_update(this,provider:str,timestamp:int) -> None:
        this._cfg['ddns'][provider]['last_update'] = timestamp


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
        return this._cfg.get('pool').get("encrypted")

    @key_filename.setter
    def  key_filename(this,path):
        this._cfg['pool']["encrypted"] = path

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
        pool = this.pool_name
        dataset = this.dataset_name

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
        pool = this.pool_name
        dataset = this.dataset_name

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

    @property
    def scrub_info(this) -> Dict[str, Any]:
        return {k: v for k, v in this._cfg['pool'].get('tools', {}).get('scrub', {}).items()}

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
    @property
    def access_account(this) -> dict:
        return this._cfg.get("access", {}).get("account", {})

    @property
    def access_services(this) -> Dict[str, SystemService]    :
        return  {k:v for k,v in this._access_services.items()}

    # SYSTEM PROPERTIES
    @property
    def system_updates(this) -> List[str]:
        return [pkg for pkg in this._cfg.get("updates", {}).get("apt", [])]

    @system_updates.setter
    def system_updates(this,updates:List[str]) -> None:
        this._cfg['updates']['apt'] = updates

    @property
    def systemd_services(this) -> List[str]:
        return [service for service in this._cfg.get('systemd',{}).get('services',[])]

    # USER PROPERTIES

    @property
    def users(this) -> List[UserProfile]:
        usernames = this._cfg.get("users", {}).keys()

        return [this.get_user(u) for u in usernames]

    @property
    def admins(this) -> List[UserProfile]:
        return [u for u in this.users if u.admin]



    # BASE METHODS

    def check_daemon(this,name:str,prefix:Optional[str]=None) -> Optional[LongWaitThread]:
        if (prefix is not None):
            name = f"{prefix}_{name}"

        if ((thread:=this._daemons.get(name))):
            if (not thread.is_running):
                if (isinstance(thread.message,Exception)):
                    raise thread.message
                else:
                    raise RuntimeError(thread.message)
            return thread

        return None

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

        ddns_def = {
            "enabled": False,
            "username": None,
            "password": None,
            "last_update": None,
        }

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
            "root": {
                "user": {
                    "otp_secret": None,
                    "fullname": "admin",
                    "permissions": ["*"],
                    "ssh_uid": 1000
                }
            },
            "access": {
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
            "vpn": {
                "peers": [],
                "endpoint": None
            },
            "ddns": {
                "noip":    ddns_def.copy(),
                "duckdns": ddns_def.copy(),
                "dynu":    ddns_def.copy(),
                "freedns": ddns_def.copy(),
                "dnsexit": ddns_def.copy(),
                "dynv6":   ddns_def.copy(),
                "cloudns": ddns_def.copy()
            },
            "systemd": {
                "services": ['nmswebapp.service','nmsbackend.service','wg-quick@wg0.service']
            }
        }

        this._cfg = cfg

        this.init_pool()

        this.flush_config()

        cmds = [
            Chmod(this.config_filename,"600",sudo=True),
            Chown("root","root",this.config_filename,sudo=True),
        ]

        LocalCommandLineTransaction(*cmds).run()

    def flush_config(this) -> None:
        this.info(f"Flushing configuration file `{this.config_filename}`")
        try:
            with open(this.config_filename,"w") as h:
                json.dump(this._cfg,h,indent=4)
                this.info(f"Configuration file `{this.config_filename}` flushed correctly")
        except Exception as e:
            this.error(f"Unable to flush the configuration file `{this.config_filename}`: {str(e)}")

    # USERS METHODS

    def user_permissions(this,username:str)->List[str]:
        return [p for p in this._cfg.get("users", {}).get(username, {}).get('permissions', [])]

    def get_user(this,username:str)->Optional[UserProfile]:
        user = this._cfg.get("users", {}).get(username, None)

        if user is not None:
            cmd = ZFSGetQuota(this.pool_name,this.dataset_name,sudo=True)
            output = cmd.execute()

            quota = None

            if (output.returncode == 0):
                for line in output.stdout.splitlines():
                    uname,used,limit = line.split("\t")

                    if (uname == username):
                        quota = Quota(used=int(used),quota=int(limit))
            else:
                this.error(f"Unable to get quota for user {username}: {output.stderr}")

            sudo = False

            cmd = Groups(username)
            output = cmd.execute()

            if (output.returncode == 0):
                sudo = "sudo" in output.stdout.strip()

            activation_token = None

            if (user.get("otp_secret") is None):
                from backend_server.v1.auth import create_token
                activation_token = create_token(
                    username=username,
                    purpose="first_login",
                    duration=525600000 #about 1000 years in minutes
                )


            return UserProfile(
                username=username,
                visible_name=user["fullname"],
                permissions=user["permissions"],
                quota = quota,
                sudo = sudo,
                admin=this.is_admin(username),
                first_login_token=activation_token
            )

    def set_user_fullname(this,username:str,fullname:str) -> None:
        this._cfg['users'][username]["fullname"] = fullname

    def change_username(this,old_username:str,new_username:str) -> None:
        this._cfg['users'][new_username] = this._cfg['users'].pop(old_username)

    def has_user_permission(this,username:str,perm:UserPermissions)->bool:
        user_permissions = this.user_permissions(username)

        if "*" in user_permissions:
            return True

        parts = perm.value.split(".")

        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in user_permissions:
                return True

            wildcard = candidate + ".*"
            if wildcard in user_permissions:
                return True

        return False

    def is_admin(this,username:str)->bool:
        return all([this.has_user_permission(username, p) for p in UserPermissions])

    def add_user(this,username:str,fullname:Optional[str],permissions:List[str],uid:int) -> None:
        this._cfg['users'][username] = {
            "otp_secret": None,
            "fullname": fullname,
            "permissions": [],
            "ssh_uid": uid
        }

        this.user_set_permissions(username,permissions)

    def user_set_permissions(this,username:str,permissions:List[str]) -> None:
        all_permissions = [p.value for p in UserPermissions]

        collapsed_permissions = collapse_permissions(permissions,all_permissions)

        for service in this._access_services.values():
            if (service.permission_hook is not None):
                if (match_permissions(collapsed_permissions,service.permission_hook)):
                    service.permission_granted(username)
                else:
                    service.permission_revoked(username)

        this._cfg['users'][username]["permissions"] = collapsed_permissions



    #AUTH/OTP METHODS

    def add_issued_token(this,token:str,expire_date:datetime.datetime) -> None:
        this._issued_tokens[token] = expire_date

    def revoke_token(this,token:str) -> None:
        del this._issued_tokens[token]

    def is_otp_configured_for(this,username:str)->bool:
        return this._cfg.get("users",{}).get(username,{}).get("otp_secret",None) is not None

    def set_temporary_otp_secret(this,username:Optional[str],secret:str) -> None:
        if (username is not None):
            if (this.is_otp_configured_for(username)):
                raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_AUTH_ALREADY_CONFIG.name))
        elif (this.is_otp_configured):
            raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_AUTH_ALREADY_CONFIG.name))

        this._tmp_secret[username] = secret


    def save_temporary_otp(this,username:Optional[str]) -> str:
        secret = this._tmp_secret[username]

        CONFIG.warning(f"I am here - temp secret: {secret}")

        if (username is not None):
            u = this._cfg.get("users",{}).get(username)
            if (u is None):
                raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_USER_NOT_FOUND.name,params=[username]))

            this._cfg["users"][username]["otp_secret"] = secret
        else:
            CONFIG.warning("right path")
            if (this.is_otp_configured):
                raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_AUTH_ALREADY_CONFIG.name))

            username = list(this._cfg.get("users",{}).keys())[0]
            CONFIG.warning(f"first username: {username}")
            this._cfg["users"][username]["otp_secret"] = secret

        this.flush_config()
        return username

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

    def config_pool(this, pool_name:str, dataset_name:str, redundancy:bool, encryption_key:Optional[str], compressed:bool, disks:List[Disk]) -> None:
        this._cfg['pool'] = {
            "name": pool_name,
            "encrypted": encryption_key,
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

    def scrub_started(this) -> None:
        this._cfg['pool']['tools']['scrub']['ongoing'] = True
        this._cfg['pool']['tools']['scrub']['last'] = datetime.datetime.now().timestamp()

    def scrub_stopped(this):
        this._cfg['pool']['tools']['scrub']['ongoing'] = False

    #DISK METHODS
    def add_disk(this,disk:Disk) -> None:
        this._cfg['pool']['disks'].append(disk.serialise())

    def replace_disk(this, old_disk:Disk, new_disk:Disk) -> None:
        idx = None

        for i,disk in enumerate(this._cfg['pool']['disks']):
            paths = [disk.get('path')]
            paths+= disk.get('physical_paths',[])

            if (old_disk.has_any_paths(paths)):
                idx = i
                break

        if (idx is not None):
            this._cfg['pool']['disks'][idx] = new_disk.serialise()

    #NET METHODS
    def vpn_remove_peer(this,idx:int) -> None:
        peers = this.vpn_peer_names
        peers.remove(this.vpn_peer_names[idx])
        this._cfg['vpn']['peers'] = peers

    def vpn_add_peer(this,name:str)->int:
        peers = this.vpn_peer_names
        peers.append(name)
        this._cfg['vpn']['peers'] = peers

        return len(peers)

    def ddns_provider_enabled(this,provider:str,enabled:bool) -> None:
        this._cfg['ddns'][provider]['enabled'] = enabled

    def ddns_config_set(this,provider:str,username:Optional[str],password:str) -> None:
        SECRET_KEY = os.environ.get("NMS_SECRET_KEY")
        digest = hashlib.sha256(SECRET_KEY.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(digest)

        fernet = Fernet(fernet_key)
        encrypted_password = fernet.encrypt(password.encode())

        this._cfg['ddns'][provider]['username'] = username
        this._cfg['ddns'][provider]['password'] = encrypted_password.decode("utf-8")

    def ddns_noip_set(this,username:str,password:str) -> None:
        this.ddns_config_set("noip",username,password)

    def ddns_duckdns_set(this,domain:str,token:str) -> None:
        this.ddns_config_set("duckdns",domain,token)

    def ddns_dynv6_set(this,domain:str,token:str) -> None:
        this.ddns_config_set("dynv6",domain,token)

    def ddns_dnsexit_set(this,host:str,apikey:str) -> None:
        this.ddns_config_set("dnsexit",host,apikey)

    def ddns_dynu_set(this, username:str, password:str) -> None:
        digest = hashlib.md5(password.encode()).hexdigest()

        this._cfg['ddns']["dynu"]['username'] = username
        this._cfg['ddns']["dynu"]['password'] = digest

    def ddns_freedns_set(this,token:str) -> None:
        this.ddns_config_set("freedns",None,token)

    def ddns_cloudns_set(this,token:str) -> None:
        this.ddns_config_set("cloudns",None,token)


    def ddns_start(this,thread_cls:Type[DDNSServiceThread],provider:str,only_token:bool=False) -> None:
        try:
            this.ddns_stop(provider)

            username = this._cfg['ddns'][provider]['username']
            password = this._cfg['ddns'][provider]['password']

            SECRET_KEY = os.environ.get("NMS_SECRET_KEY")
            digest = hashlib.sha256(SECRET_KEY.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(digest)

            fernet = Fernet(fernet_key)
            decrypted_password = fernet.decrypt(password.encode()).decode("utf-8")

            thread = thread_cls(decrypted_password) if only_token else thread_cls(username, decrypted_password)
            thread.start()
            this._daemons[f"ddns_{provider}"] = thread

            this.ddns_provider_enabled(provider, True)
        except (AttributeError, ValueError):
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_DDNS_CONFIG.name))



    def ddns_noip_start(this):
        this.ddns_start(DDNSNoIP,"noip")

    def ddns_duckdns_start(this):
        this.ddns_start(DuckDNS,"duckdns")

    def ddns_dynv6_start(this):
        this.ddns_start(Dynv6, "dynv6")

    def ddns_dnsexit_start(this):
        this.ddns_start(DNSExit,"dnsexit")

    def ddns_dynu_start(this):
        provider = "dynu"
        this.ddns_stop(provider)

        username = this._cfg['ddns'][provider]['username']
        password = this._cfg['ddns'][provider]['password']


        thread = DynuDDNS(username, password)
        thread.start()
        this._daemons[f"ddns_{provider}"] = thread

        this.ddns_provider_enabled(provider, True)

    def ddns_freedns_start(this) -> None:
        this.ddns_start(FreeDNS,"freedns",True)

    def ddns_cloudns_start(this) -> None:
        this.ddns_start(ClouDNS,"cloudns",True)


    def ddns_stop(this,provider:str) -> None:
        thread_name = f"ddns_{provider}"
        if (thread_name in this._daemons):
            this._daemons[thread_name].stop()
            del this._daemons[thread_name]

        this.ddns_provider_enabled(provider,False)

    def _ddns_init(this) -> None:
        for k,v in this._cfg['ddns'].items():
            if (v.get('enabled',False) == True):
                method = f"ddns_{k}_start"

                if (hasattr(this,method)):
                    mtd = getattr(this,method)
                    mtd()






CONFIG = NMSConfig()