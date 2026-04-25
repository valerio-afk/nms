from backend_server.utils.cmdl import Chown, LocalCommandLineTransaction, Groups, ZPoolList, GetEntPasswd, ZFSSnapshot
from backend_server.utils.cmdl import ZFSList, ZPoolStatus, LSBLK, ZFSGet,  ZFSGetQuota, Chmod, ZFSRollback, ZFSDestroy
from backend_server.utils.cmdl import UserAdd, GetUserUID, ReadLink, Find
from backend_server.utils.enums import DistroFamilies
from backend_server.utils.logger import Logger
from backend_server.utils.responses import ErrorMessage, UserProfile, Quota
from backend_server.utils.services import SystemService
from backend_server.utils.threads import FreeDNS, DNSExit, Dynv6, ClouDNS, FreeOldChunkFiles
from backend_server.utils.threads import NetIOCounter, DDNSNoIP, LongWaitThread, DDNSServiceThread, DuckDNS, DynuDDNS
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
from fastapi import HTTPException
from importlib import import_module
from backend_server.utils.events import EVENT_MANAGER, Events, EventContext
from nms_shared import ErrorMessages
from nms_shared.disks import Disk
from nms_shared.enums import DiskStatus, UserPermissions
from nms_shared.utils import match_permissions
from typing import Optional, Dict, List, Any, Type, Tuple
import base64
import hashlib
import json
import jwt
import os
import pytz
import re
import uuid

SECRET_KEY = os.environ.get("NMS_SECRET_KEY")

def _create_token(username: str, purpose: str, duration: int) -> Tuple[str, float]:
    duration = min(duration,60*24*3) # duration always capped to 3 days

    released = datetime.now(pytz.timezone("UTC"))
    expire = released + timedelta(minutes=duration)
    expire_timestamp = expire.timestamp()

    payload = {"username": username, "purpose": purpose, "released": released.timestamp(), "exp": expire_timestamp}

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    return encoded_jwt, expire_timestamp


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

def create_system_user(username: str, permissions: List[str], sudo: bool = False) -> int:
    def_groups = ['users']
    if (CONFIG.distro_family == DistroFamilies.DEB):
        def_groups.extend(['plugdev', 'netdev'])

    if (UserPermissions.SERVICES_SMB_ACCESS.name in permissions):
        def_groups.append('sambashare')
    if (sudo):
        def_groups.append(CONFIG.sudo_group)

    allow_login = UserPermissions.SERVICES_SSH_ACCESS.name in permissions
    home_dir = os.path.join(CONFIG.mountpoint, username) if CONFIG.mountpoint is not None else None

    cmd = UserAdd(username, def_groups, home_dir, allow_login,sudo=True).execute()

    if (cmd.returncode != 0):
        raise Exception(cmd.stderr)

    if (home_dir is not None):
        cmds = [
            Chown(username, username, home_dir, ['-R']),
            Chmod(home_dir, "0700", ['-R'])
        ]

        trans = LocalCommandLineTransaction(*cmds, privileged=True)
        output = trans.run()

        if (not trans.success):
            errors = "\n".join([o['stderr'].strip() for o in output])
            raise Exception(errors)

    uid = GetUserUID(username).execute()

    if (uid.returncode != 0):
        raise Exception(uid.stderr)

    return int(uid.stdout)



def detect_distro_family() -> DistroFamilies:
    os_release = {}

    try:
        with open("/etc/os-release","r") as f:
            for line in f:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os_release[key] = value.strip('"')
    except FileNotFoundError:
        return DistroFamilies.UNK

    id_like = os_release.get("ID_LIKE", "").lower()
    distro_id = os_release.get("ID", "").lower()

    # First try ID_LIKE
    if (("debian" in id_like) or (distro_id in ("debian", "ubuntu", "raspbian"))):
        return DistroFamilies.DEB
    if any(x in id_like for x in ("rhel", "fedora")) or (distro_id in ("rhel", "fedora", "centos", "rocky", "almalinux")):
        return DistroFamilies.RH

    return DistroFamilies.UNK




class NMSConfig(Logger):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(NMSConfig, cls).__new__(cls)
        return cls.instance

    def __init__(this, config_file:str='nms.json'):
        super().__init__()

        if (SECRET_KEY is None):
            raise Exception("Invalid secret key. Please provide a secret key as environmental variable NMS_SECRET_KEY.")

        this._config_file = config_file
        this._cfg = {}
        this._tmp_secret = {}
        this._uploads={}
        this._distro = detect_distro_family()

        try:
            this.load_configuration_file()
        except FileNotFoundError:
            this.create_default_config_file()

        this._daemons = {
            'netcounter': NetIOCounter(),
            'chunk_delete': FreeOldChunkFiles(this.mountpoint)
        }

        for d in this._daemons.values():
            d.start()

        this._access_services = {}
        this._issued_tokens = {}

        this._setup_access_services()
        this._ddns_init()
        this._register_events()

        this.trigger_event(Events.SYSTEM_STARTUP)

    def _register_events(this) -> None:
        for uuid in this._cfg.get("events", {}).keys():
            this.register_event(uuid)


    def _setup_access_services(this) -> None:
        module = import_module("backend_server.utils.services")


        for service,args in this._cfg.get("access",{}).get("services",{}).items():
            try:
                cls = getattr(module,f"{service.upper()}Service")
                arguments = args.copy()
                arguments['mountpoint'] = this.mountpoint
                arguments['os'] = this.distro_family
                this._access_services[service] = cls(**arguments)
            except AttributeError as e:
                ... #service not implemented yet


        for admin in this.admins:
            for service in this.access_services.values():
                service.permission_granted(admin.username)



    #BASE PROPERTIES

    @property
    def config_filename(this) -> str:
        return this._config_file

    @property
    def distro_family(this) -> DistroFamilies:
        return this._distro

    @property
    def sudo_group(this) -> str:
        if (this.distro_family == DistroFamilies.DEB):
            return "sudo"
        return "wheel"

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

        return {u.username:secret
                for u in this.admins
                if (secret:=this._cfg.get("users",{}).get(u.username).get("otp_secret")) is not None
                }

    @property
    def issued_tokens(this) -> List[str]:
        now = datetime.now().timestamp()
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
            return None

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
        if ((pool_name:= this._cfg.get('pool',{}).get("name", None)) is None):
            return False
        cmd = ZPoolStatus().execute()

        if (cmd.returncode != 0):
            return False

        d = json.loads(cmd.stdout)

        return len(d.get("pools",{})) > 0


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
        return [pkg for pkg in this._cfg.get("updates", {}).get("apt", {}).get("packages",[])]

    @system_updates.setter
    def system_updates(this,updates:List[str]) -> None:
        this._cfg['updates']['apt']['packages'] = updates

    @property
    def last_apt(this) -> int:
        return this._cfg.get("updates", {}).get("apt", {}).get("last")

    @last_apt.setter
    def last_apt(this,last:int) -> None:
        this._cfg['updates']['apt']['last'] = last

    @property
    def systemd_services(this) -> List[str]:
        return [service for service in this._cfg.get('systemd',{}).get('services',[])]

    @property
    def nms_updates(this) -> Optional[Dict[str, str]]:
        return this._cfg.get("updates", {}).get("releases")

    # USER PROPERTIES

    @property
    def users(this) -> List[UserProfile]:
        usernames = this._cfg.get("users", {}).keys()

        return [this.get_user(u) for u in usernames]

    @property
    def admins(this) -> List[UserProfile]:
        return [u for u in this.users if u.admin]

    #EVENTS PROPERTIES
    @property
    def registered_events(this) -> List[Dict[str, Any]]:
        return this._cfg.get("events", {}).copy()

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

        smb_daemon_suffix = "d" if this.distro_family == DistroFamilies.DEB else ""
        ssh_daemon_suffix = "d" if this.distro_family == DistroFamilies.RH else ""

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
            "users": {
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
                            "service_name": f"ssh{ssh_daemon_suffix}.service",
                        },
                        "ftp": {
                            "service_name": "vsftpd.service"
                        },
                        "nfs": {"service_name":["rpcbind.service","nfs-server.service"]},
                        "smb": {"service_name":[f"smb{smb_daemon_suffix}.service",f"nmb{smb_daemon_suffix}.service"]},
                        'web': {
                            "service_name": "nginx.service"
                        }
                    }
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
                "services": ['nginx.service','nmswebapp.service','nmsbackend.service','wg-quick@wg0.service']
            },
            "events":{},
            "updates": {
                "apt": {
                    "last": None,
                    "packages": []
                },
                "releases": None
            },
        }

        this._cfg = cfg

        this.init_pool()

        this.flush_config()

        cmds = [
            Chmod(this.config_filename,"600",sudo=True),
            Chown("backend","backend",this.config_filename,sudo=True),
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

    def reset_otp(this,username:str) -> None:
        tokens = [x for x in this._issued_tokens.keys()]

        for token in tokens:
            payload = jwt.decode(token, SECRET_KEY, algorithms="HS256")
            if payload["username"] == username:
                this.revoke_token(token)

        this._cfg['users'][username]['otp_secret'] = None

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
                sudo = this.sudo_group in output.stdout.strip()

            activation_token = None

            if (user.get("otp_secret") is None):
                activation_token,exp_time = _create_token(
                    username=username,
                    purpose="first_login",
                    duration=60*24 #about 1 day
                )
                this.add_issued_token(activation_token,exp_time)

            getend_cmd = GetEntPasswd(username).execute()
            home_dir = None

            if (getend_cmd.returncode == 0):
                tokens =getend_cmd.stdout.strip().split(":")
                home_dir = tokens[5]

            uid = None

            cmd = GetEntPasswd(username).execute()
            if (cmd.returncode == 0):
                token = cmd.stdout.strip().split(":")
                uid = int(token[2])

            return UserProfile(
                username=username,
                visible_name=user["fullname"],
                permissions=user["permissions"],
                quota = quota,
                sudo = sudo,
                admin=this.is_admin(username),
                first_login_token=activation_token,
                home_dir=home_dir,
                uid=uid
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

    def delete_user(this,username:str)->None:
        del this._cfg['users'][username]

        for service in this._access_services.values():
            service.remove_user(username)

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

    def add_issued_token(this,token:str,expire_date:float) -> None:
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

        if (username is not None):
            u = this._cfg.get("users",{}).get(username)
            if (u is None):
                raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_USER_NOT_FOUND.name,params=[username]))

            this._cfg["users"][username]["otp_secret"] = secret
            del this._tmp_secret[username]
        else:
            if (this.is_otp_configured):
                raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_AUTH_ALREADY_CONFIG.name))

            for u,d in this._cfg.get("users",{}).items():
                if ((len(perms:=d.get("permissions",[]))>0) and perms[0]=="*"):
                    username = u

            if (username is None):
                raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_USER_NOT_FOUND.name,params=['admin user']))

            this._cfg["users"][username]["otp_secret"] = secret
            del this._tmp_secret[None]


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

                this.warning(str(disks))
                this.warning(str(block_devices))

                for dev in disks:
                    #check if dev is a symlink or a block special file
                    find_result = Find("/dev/disk",name=dev,sudo=True).execute()

                    if ((find_result is not None) and (find_result.returncode==0)):
                        symlinks = find_result.stdout.splitlines()

                        if (len(symlinks)>0):
                            #take first
                            symlink = symlinks[0]

                            readlink_result = ReadLink(symlink,sudo=True).execute()

                            if ((readlink_result is not None) and (readlink_result.returncode==0)):
                                _,dev = os.path.split(readlink_result.stdout.strip())

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

    def create_snapshot(this,snapshot_name:str) -> None:
        regex = re.compile("^[A-Za-z0-9_.:-]+$")
        snapshot_name = snapshot_name.strip()

        if (regex.match(snapshot_name) is None):
            raise HTTPException(status_code=400,
                                detail=ErrorMessage(code=ErrorMessages.E_POOL_SNAPSHOT_NAME.name,params=[snapshot_name])
                                )

        zfs = ZFSSnapshot(pool=this.pool_name,dataset=this.dataset_name,snapshot_name=snapshot_name).execute()

        if (zfs.returncode != 0):
            raise HTTPException(status_code=400,
                                detail=ErrorMessage(code=ErrorMessages.E_POOL_SNAPSHOT_CREATE.name,
                                                    params=[zfs.stderr])
                                )

    def delete_snapshot(this,snapshot_name:str) -> None:
        snapshot_name = snapshot_name.strip()
        zfs = ZFSDestroy(pool=this.pool_name,dataset=this.dataset_name,snapshot_name=snapshot_name).execute()

        if (zfs.returncode != 0):
            raise HTTPException(status_code=400,
                                detail=ErrorMessage(code=ErrorMessages.E_POOL_SNAPSHOT_DELETE.name,
                                                    params=[zfs.stderr])
                                )

    def rollback_snapshot(this,snapshot_name:str) -> None:
        snapshot_name = snapshot_name.strip()

        zfs = ZFSRollback(pool=this.pool_name,dataset=this.dataset_name,snapshot_name=snapshot_name).execute()

        if (zfs.returncode != 0):
            raise HTTPException(status_code=400,
                                detail=ErrorMessage(code=ErrorMessages.E_POOL_SNAPSHOT_ROLLBACK.name,
                                                    params=[zfs.stderr])
                                )


    def scrub_started(this) -> None:
        this._cfg['pool']['tools']['scrub']['ongoing'] = True
        this._cfg['pool']['tools']['scrub']['last'] = datetime.now().timestamp()

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

    #FS METHODS
    def init_upload(this,length:int,metadata:Any) -> str:
        upload_id = str(uuid.uuid4())
        this._uploads[upload_id] = {
            "length":length,
            "offset":0,
            "metadata": metadata
        }

        return upload_id


    def get_upload_session(this, id:str) -> dict:
        return this._uploads.get(id)

    def increment_upload_offset(this, id: str, length:int, reset:bool=False) -> int:
        if (reset):
            this._uploads[id]["offset"] = length
        else:
            this._uploads[id]["offset"] += length

        return this._uploads[id]["offset"]

    def delete_upload_session(this, id:str) -> None:
        del this._uploads[id]

    def is_upload_complete(this,id:str) -> bool:
        return this._uploads[id]['offset'] == this._uploads[id]['length']

    #SYSTEM METHODS
    def new_nms_update(this,version:str,tarball_url:str) -> None:
        from backend_server import __version__ as ver

        nms = this._cfg['updates'].get('releases')
        new_update = False

        if (nms is None):
            if (version != ver):
                new_update = True
        else:
            if (nms.get('version') != ver):
                new_update = True

        if (new_update):
            this._cfg['updates']['releases'] = {
                "version": version,
                "tarball_url": tarball_url
            }

    def clean_nms_update(this) -> None:
        this._cfg['updates']['releases'] = None

    # EVENT METHODS

    def add_event(this,event_name:str,action_name:str,parameters:Dict[str,dict]) -> None:
        id = str(uuid.uuid4())

        this._cfg['events'][id] = {
            "name": event_name,
            "action": action_name,
            "enabled": True,
        }

        this._cfg['events'][id]['parameters'] = parameters

        this.register_event(id)

    def register_event(this,uuid:str)->None:
        specs = this._cfg.get("events", {}).get(uuid)
        if (specs is not None):
            if (specs.get("enabled",False)):
                EVENT_MANAGER.register_action(
                    uuid=uuid,
                    event_tag=specs.get("name"),
                    action_tag=specs.get("action"),
                    action_parameters=specs.get("parameters",{}).get("action_parameters",{}),
                    event_parameters = specs.get("parameters",{}).get("event_parameters",{}),
                    mountpoint=this.mountpoint,
                )

            this.info(f"Event {uuid} registered successfully")
        else:
            this.warning(f"Invalid event {uuid} ")

    def unregister_event(this,uuid:str)->None:
        EVENT_MANAGER.unregister_action(uuid)
        this.info(f"Event {uuid} unregistered successfully")

    def enable_event(this,uuid:str)->None:
        if ((e:=this._cfg['events'].get(uuid)) is not None):
            e["enabled"] = True
            this.register_event(uuid)

    def disable_event(this,uuid:str)->None:
        if ((e:=this._cfg['events'].get(uuid)) is not None):
            e["enabled"] = False
            this.unregister_event(uuid)

    def trigger_event(this,event:Events,ctx:Optional[Dict[str,Any]]=None) -> None:

        import sys
        print(ctx,file=sys.stderr)

        callbacks = {k:(lambda x=v: x) for k,v in ctx.items()} if ctx is not None else {}

        callbacks.setdefault(EventContext.USER.name,lambda : this.users)

        triggered = EVENT_MANAGER.trigger(event,callbacks)

        uuids = [t['uuid'] for t in triggered]

        this.info(f"Event triggered: {event.value} - Actions Executed: {', '.join(uuids) if len(uuids)>0 else 'None'}")

    def trigger_event_by_uuid(this, uuid:str, ctx: Optional[Dict[str, Any]] = None) -> None:
        event = this._cfg['events'].get(uuid,None)

        if ((event is not None) and ("name" in event.keys())):
            this.trigger_event(Events(event['name']),ctx)

    def update_event_parameters(this,uuid:str, parameters:Dict[str,Any]) -> None:
        current_parameters = this._cfg['events'].get(uuid).get("parameters",{}).copy()

        if (len(current_parameters)==0):
            raise AttributeError()

        for k1,k2 in zip(current_parameters.keys(),parameters.keys()):
            if (k1!=k2):
                raise KeyError(k2)


        this._cfg['events'][uuid]['parameters'] = parameters


    def delete_event(this,uuid:str)->None:
        this.unregister_event(uuid)
        if (this._cfg['events'].get(uuid) is not None):
            del this._cfg['events'][uuid]


CONFIG = NMSConfig()