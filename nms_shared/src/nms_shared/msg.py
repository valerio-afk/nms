from enum import Enum
from flask_babel import _
from typing import Callable, Optional


def parse_msg(msg:Optional[Callable[...,str]],*args,**kwargs) -> str:
    return str(msg(*args,**kwargs)) if msg is not None else "-"


class ErrorMessages(Enum):
    E_UNKNOWN = "E_UNKNOWN"
    E_UNKNOWN_RESPONSE = "E_UNKNOWN_RESPONSE"
    E_PROPERTY = "E_PROPERTY"
    E_CSRF = "E_CSRF"
    E_UNKNOWN_METHOD = "E_UNKNOWN_METHOD"
    E_READ_FILE = "E_READ_FILE"
    E_SELINUX_PORT = "E_SELINUX_PORT"
    E_SYSTEMD_START = "E_SYSTEMD_START"
    E_SYSTEMD_STOP = "E_SYSTEMD_STOP"

    E_POOL_ALREADY_CONF = "E_POOL_ALREADY_CONF"
    E_POOL_NO_CONF = "E_POOL_NO_CONF"
    E_POOL_CONFIG = "E_POOL_CONFIG"
    E_POOL_DISK_UNAVAL = "E_POOL_DISK_UNAVAL"
    E_POOL_NEW = "E_POOL_NEW"
    E_POOL_DESTROY = "E_POOL_DESTROY"
    E_POOL_REDUNDANCY_MIN = "E_POOL_REDUNDANCY_MIN"
    E_POOL_EXPAND = "E_POOL_EXPAND"
    E_POOL_EXPAND_INFO = "E_POOL_EXPAND_INFO"
    E_POOL_EXPAND_STATUS = "E_POOL_EXPAND_STATUS"
    E_POOL_KEY = "E_POOL_KEY"
    E_POOL_KEY_IMPORT = "E_POOL_KEY_IMPORT"
    E_POOL_LIST = "E_POOL_LIST"
    E_POOL_RECOVERY = "E_POOL_RECOVERY"
    E_POOL_DISKS = "E_POOL_DISKS"
    E_POOL_DISK_REPLACE = "E_POOL_DISK_REPLACE"
    E_POOL_ATTACH = "E_POOL_DETACH"
    E_POOL_DETACH = "E_POOL_DETACH"
    E_POOL_MOUNT = "E_POOL_MOUNT"
    E_POOL_UNMOUNT = "E_POOL_UNMOUNT"
    E_POOL_MOUNTED = "E_POOL_MOUNTED"
    E_POOL_UNMOUNTED = "E_POOL_UNMOUNTED"
    E_POOL_SCRUB = "E_POOL_SCRUB"
    E_POOL_RM_MOUNTPOINT = "E_POOL_RM_MOUNTPOINT"
    E_POOL_INVALID_MOUNTPOINT = "E_POOL_INVALID_MOUNTPOINT"
    E_POOL_MOUNT_STATUS = "E_POOL_MOUNT_STATUS"
    E_POOL_MOUNTPOINT = "E_POOL_MOUNTPOINT"
    E_POOL_FORMAT = "E_POOL_FORMAT"
    E_POOL_CAPACITY = "E_POOL_CAPACITY"
    E_POOL_OPENED = "E_POOL_OPENED"
    E_POOL_DISK_MISSING = "E_POOL_DISK_MISSING"
    E_POOL_CORRUPTED = "E_POOL_CORRUPTED"
    E_POOL_OUTDATED = "E_POOL_OUTDATED"
    E_POOL_SNAPSHOT_NAME = "E_POOL_SNAPSHOT_NAME"
    E_POOL_SNAPSHOT_CREATE = "E_POOL_SNAPSHOT_CREATE"
    E_POOL_SNAPSHOT_DELETE = "E_POOL_SNAPSHOT_DELETE"
    E_POOL_SNAPSHOTS = "E_POOL_SNAPSHOTS"
    E_POOL_SNAPSHOT_ROLLBACK = "E_POOL_SNAPSHOT_ROLLBACK"

    E_AUTH_ALREADY_CONFIG = "E_AUTH_ALREADY_CONFIG"
    E_AUTH_INVALID = "E_AUTH_INVALID"
    E_AUTH_EXPIRED = "E_AUTH_EXPIRED"
    E_AUTH_REVOKED = "E_AUTH_REVOKED"
    E_AUTH_MALFORMED = "E_AUTH_MALFORMED"
    E_AUTH_NOT_CONF = "E_AUTH_NOT_CONF"
    E_AUTH_WRONG_OTP = "E_AUTH_WRONG_OTP"

    E_DISK_ATTACH = "E_DISK_ATTACH"
    E_DISK_FORMAT = "E_DISK_FORMAT"
    E_DISK_SELF_TEST = "E_DISK_SELF_TEST"

    E_FS_CH_PERM =  "E_FS_CH_PERM"

    E_APT_GET = "E_APT_GET"
    E_APT_UNK = "E_APT_UNK"

    E_ACCESS_ENABLED = "E_ACCESS_ENABLED"
    E_ACCESS_DISABLED = "E_ACCESS_DISABLED"
    E_ACCESS_DISABLING = "E_ACCESS_DISABLING"
    E_ACCESS_SERV_UNK = "E_ACCESS_SERV_UNK"
    E_ACCESS_PROP = "E_ACCESS_PROP"

    E_NET_CHANGE_STATE = "E_NET_CHANGE_STATE"
    E_NET_CONNECTION_STATUS = "E_NET_CONNECTION_STATUS"
    E_NET_INVALID_NETMASK = "E_NET_INVALID_NETMASK"
    E_NET_INVALID_IP_ADDRESS = "E_NET_INVALID_IP_ADDRESS"
    E_NET_INVALID_GATEWAY = "E_NET_INVALID_GATEWAY"
    E_NET_INVALID_DNS = "E_NET_INVALID_DNS"
    E_NET_WIFI_LIST = "E_NET_WIFI_LIST"
    E_NET_WIFI_CONNECT = "E_NET_WIFI_CONNECT"
    E_NET_WIFI_DEV = "E_NET_WIFI_DEV"
    E_NET_AP = "E_NET_AP"
    E_NET_VPN_NOTCONF = "E_NET_VPN_NOTCONF"
    E_NET_VPN_STATE = "E_NET_VPN_STATE"
    E_NET_VPN_KEY = "E_VPN_KEY"
    E_NET_VPN_GEN_PRIVATE = "E_VPN_GEN_PRIVATE"
    E_NET_VPN_GEN_PUBLIC = "E_VPN_GEN_PUBLIC"
    E_NET_VPN_CONF = "E_NET_VPN_CONF"
    E_NET_VPN_USER = "E_VPN_USER"
    E_NET_VPN_USER_INVALID = "E_VPN_USER_INVALID"
    E_NET_VPN_IP_MAX = "E_VPN_IP_MAX"
    E_NET_DDNS_INVALID = "E_NET_DDNS_INVALID"
    E_NET_DDNS_SERVICE = "E_NET_DDNS_SERVICE"
    E_NET_DDNS_CONFIG = "E_NET_DDNS_CONFIG"

    E_USER_NOT_FOUND = "E_USER_NOT_FOUND"
    E_USER_PASSWD = "E_USER_PASSWD"
    E_USER_QUOTA = "E_USER_QUOTA"
    E_USER_NAME = "E_USER_NAME"
    E_USER_SUDO = "E_USER_SUDO"
    E_NEW_USER = "E_NEW_USER"
    E_PERM_ADMIN = "E_PERM_ADMIN"
    E_DEL_ADMIN = "E_DEL_ADMIN"
    E_USER_COPY_FILES = "E_USER_COPY_FILES"
    E_USER_DELETE = "E_USER_DELETE"
    E_USER_LOGIN_RESET = "E_USER_LOGIN_RESET"
    E_USER_SYSTEM = "E_USER_SYSTEM"

    E_SYSTEM_UPDATES = "E_SYSTEM_UPDATES"
    E_SYSTEM_DIST = "E_SYSTEM_DIST"

    E_FS_NOT_FILE = "E_FS_NOT_FILE"
    E_FS_ZIP = "E_FS_ZIP"
    E_FS_UNZIP = "E_FS_UNZIP"
    E_REL_PATH = "E_REL_PATH"
    E_FS_COPY = "E_FS_COPY"
    E_FS_MOVE = "E_FS_MOVE"
    E_FS_MKDIR = "E_FS_MKDIR"

    E_EVENT_INVALID = "E_EVENT_INVALID"
    E_ACTION_INVALID = "E_ACTION_INVAID"
    E_EVENT_INVALID_ACTION = "E_EVENT_INVALID_ACTION"
    E_EVENT_INVALID_PARAM = "E_EVENT_INVALID_PARAM"

    @staticmethod
    def get_error_from_string(error_code:str,*args,**kwargs) -> str:
        return ErrorMessages.get_error(ErrorMessages[error_code],*args,**kwargs)

    @staticmethod
    def get_error(err_code:"ErrorMessage",*args,**kwargs) -> str:
        return parse_msg(ERROR_MESSAGES[err_code],*args,**kwargs)

    @staticmethod
    def fallback_message():
        return ErrorMessages.get_error(ErrorMessages.E_UNKNOWN)
    
class WarningMessages(Enum):
    W_POOL_OPENED = "W_POOL_OPENED"
    W_POOL_MISSING = "W_POOL_MISSING"
    W_POOL_CORRUPTED = "W_POOL_CORRUPTED"
    W_POOL_NEEDED = "W_POOL_NEEDED"
    W_DISK_ISSUE = "W_DISK_ISSUE"
    W_DISK_FORMAT = "W_DISK_FORMAT"
    W_POOL_DISK_OFFLINE = "W_POOL_DISK_OFFLINE"
    W_NEW_USER = "W_NEW_USER"
    W_USER_NO_UID = "W_USER_NO_UID"


    @staticmethod
    def get_warning(warn_code: "WarningMessages", *args, **kwargs) -> str:
        return parse_msg(WARNING_MESSAGES[warn_code], *args, **kwargs)

    @staticmethod
    def get_warning_from_string(code:str,*args,**kwargs) -> str:
        return WarningMessages.get_warning(WarningMessages[code],*args,**kwargs)

class SuccessMessages(Enum):
    S_POOL_CREATED = "S_POOL_CREATED"
    S_POOL_EXPANDED = "S_POOL_EXPANDED"
    S_POOL_FORMATTED = "S_POOL_FORMATTED"
    S_POOL_DESTROYED = "S_POOL_DESTROYED"
    S_POOL_MOUNTED = "S_POOL_MOUNTED"
    S_POOL_UNMOUNTED = "S_POOL_UNMOUNTED"
    S_POOL_SCRUB = "S_POOL_SCRUB"
    S_POOL_SNAPSHOT_CREATE = "S_POOL_SNAPSHOT_CREATE"
    S_POOL_SNAPSHOT_DELETE = "S_POOL_SNAPSHOT_DELETE"
    S_POOL_SNAPSHOT_ROLLBACK = "S_POOL_SNAPSHOT_ROLLBACK"

    S_APT_UPDATE = "S_APT_UPDATE"
    S_APT_UPGRADE = "S_APT_UPGRADE"

    S_OTP_DANGEROUS = "S_OTP_DANGEROUS"

    S_RECOVERY = "S_RECOVERY"

    S_ACCESS_ENABLED = "S_ACCESS_ENABLED"
    S_ACCESS_UPDATED = "S_ACCESS_UPDATED"
    S_ACCESS_DISABLED = "S_ACCESS_DISABLED"

    S_DISK_FORMATTED = "S_DISK_FORMATTED"
    S_DISK_SELF_TEST = "S_DISK_SELF_TEST"

    S_POOL_REPLACE_DISK = "S_POOL_REPLACE_DISK"

    S_NET_VPN_KEYSGEN = "S_VPN_KEYSGEN"
    S_NET_VPN_CONFIG = "S_VPN_CONFIG"
    S_NET_CONFIG = "S_NET_CONFIG"
    S_NET_VPN_PEER_DELETED = "S_NET_VPN_PEER_DELETED"
    S_NET_VPN_PEER_ADDED = "S_NET_VPN_PEER_ADDED"
    S_NET_DDNS_ENABLED = "S_NET_DDNS_ENABLED"
    S_NET_DDNS_DISABLED = "S_NET_DDNS_DISABLED"
    S_NET_AP = "S_NET_AP"

    S_USER_PASSWORD = "S_USER_PASSWORD"
    S_USER_FULLNAME = "S_USER_FULLNAME"
    S_USER_QUOTA = "S_USER_QUOTA"
    S_USER_NAME = "S_USER_NAME"
    S_USER_SUDO = "S_USER_SUDO"
    S_NEW_USER = "S_NEW_USER"
    S_USER_PERM = "S_USER_PERM"
    S_DEL_USER = "S_DEL_USER"
    S_USER_LOGIN_RESET = "E_USER_LOGIN_RESET"

    S_EVENT_ADDED = "S_EVENT_ADDED"
    S_EVENT_ENABLED = "S_EVENT_ENABLED"
    S_EVENT_DISABLED = "S_EVENT_DISABLED"
    S_EVENT_DELETED = "S_EVENT_DELETED"
    S_EVENT_UPDATED = "S_EVENT_UPDATED"


    @staticmethod
    def get_message(success_code:"SuccessMessage",*args,**kwargs) -> str:
        return parse_msg(SUCCESS_MESSAGES[success_code],*args,**kwargs)

    @staticmethod
    def get_success_from_string(code:str,*args,**kwargs) -> str:
        return SuccessMessages.get_message(SuccessMessages[code],*args,**kwargs)

class InfoMessages(Enum):
    I_POOL_EXPANSION_ETA = "I_POOL_EXPANSION_ETA"
    I_POOL_EXPANSION = "I_POOL_EXPANSION"
    I_POOL_DISK_REPLACEMENT = "I_POOL_DISK_REPLACEMENT"

    @staticmethod
    def get_message(code:"InfoMessages",*args,**kwargs) -> str:
        return parse_msg(INFO_MESSAGES[code],*args,**kwargs)


class EventNames(Enum):
    SYSTEM = "system"
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_REBOOT = "system.reboot"
    SYSTEM_POWEROFF = "system.poweroff"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_SYSTEMD = "system.systemd"
    SYSTEM_UPDATES = "system.updates"
    SYSTEM_UPGRADE = "system.upgrade"

    USER = "user"
    USER_LOGGED_IN = "user.logged_in"
    USER_CREATED = "user.created"
    USER_DELETED = "user.deleted"


    DISK = "disk"
    DISK_MOUNT = "disk.mount"
    DISK_UNMOUNT = "disk.unmount"

    ACCESS = "access"
    ACCESS_ENABLED = "access.enabled"
    ACCESS_DISABLED = "access.disabled"

    NETWORK = "net"
    VPN_ENABLED = "net.vpn_enabled"
    VPN_DISABLED = "net.vpn_disabled"

    TIMER = "timer"
    TIMER_MINUTES = "timer.minutes"

    FILE = "file"
    FILE_CREATED = "file.created"
    FILE_DELETED = "file.deleted"
    FILE_MODIFIED = "file.modified"


    @staticmethod
    def get_event(tag: "EventNames", *args, **kwargs) -> str:
        return parse_msg(EVENT_NAMES[tag], *args, **kwargs)


ERROR_MESSAGES = {
    ErrorMessages.E_UNKNOWN : lambda: _("Unknown Error"),
    ErrorMessages.E_UNKNOWN_RESPONSE : lambda: _("Unknown response from server"),
    ErrorMessages.E_PROPERTY : lambda prop, info: _("Error while getting %(prop)s: %(info)s") % {'prop': prop, 'info': info},
    ErrorMessages.E_CSRF : lambda : _("Form validation failed"),
    ErrorMessages.E_UNKNOWN_METHOD : lambda : _("Unknown operation."),
    ErrorMessages.E_READ_FILE : lambda f,info : _("Unable to read the file %(file)s: %(info)s") % {"file":f,'info':info},
    ErrorMessages.E_REL_PATH : lambda path1, path2: _("Path `%(path1)s` is not relative to `%(path2)s`") % {"path1":path1, 'path2':path2},
    ErrorMessages.E_SELINUX_PORT: lambda info : _("Error while obtaining system information on ports: %(info)s") % {"info":info},
    ErrorMessages.E_SYSTEMD_START: lambda services,info : _("Error while starting the system service(s) %(services)s: %(info)s") % {"info":info,'services':services},
    ErrorMessages.E_SYSTEMD_STOP: lambda services,info : _("Error while stopping the system service(s) %(services)s: %(info)s") % {"info":info,'services':services},

    ErrorMessages.E_POOL_ALREADY_CONF : lambda: _("The disk array is already configured."),
    ErrorMessages.E_POOL_NO_CONF : lambda: _("Disk array not configured yet."),
    ErrorMessages.E_POOL_CONFIG : lambda: _("Disk array is configured."),
    ErrorMessages.E_POOL_DISK_UNAVAL : lambda dev : _("Disk %(dev)s is not available to be in the new disk array.") % {'dev':dev},
    ErrorMessages.E_POOL_NEW : lambda info = None: _("Unable to create a new disk array: %(info)s") % {'info': info or ErrorMessages.fallback_message()},
    ErrorMessages.E_POOL_DESTROY : lambda info = None: _("Unable to destroy the disk array: %(info)s") % {'info': info or ErrorMessages.fallback_message()},
    ErrorMessages.E_POOL_REDUNDANCY_MIN : lambda: _("You must have at least 3 disks connected to opt in redundancy."),
    ErrorMessages.E_POOL_EXPAND : lambda dev, info: _("Error while adding %(dev)s: %(info)s") % {'dev': dev, 'info': info},
    ErrorMessages.E_POOL_EXPAND_INFO : lambda dev: _("Could not retrieve information for the disk: %(dev)s") % {'dev': dev},
    ErrorMessages.E_POOL_EXPAND_STATUS : lambda info: _("Unable to get array expansion status: %(info)s") % {'info': info},
    ErrorMessages.E_POOL_KEY : lambda info = None: _("Error while retrieving the encryption key: %(info)s") % {'info': info or ErrorMessages.fallback_message()},
    ErrorMessages.E_POOL_KEY_IMPORT : lambda info: _("Error while importing the encryption key: %(info)s") % {'info': info },
    ErrorMessages.E_POOL_ATTACH : lambda info: _("Error while attaching an existing pool: %(info)s") % {'info': info},
    ErrorMessages.E_POOL_LIST : lambda info: _("Unable to retrieve the list of pools."),
    ErrorMessages.E_POOL_RECOVERY : lambda info: _("Error while recovering the disk array: %(info)s") % {'info': info},
    ErrorMessages.E_POOL_DISKS : lambda info: _("Error while retrieving the disks in the array: %(info)s") % {'info': info},
    ErrorMessages.E_POOL_DISK_REPLACE : lambda d1,d2,info: _("Unable to replace %(dev1)s with %(dev2)s: %(info)s") % {'dev1':d1, 'dev2': d2, 'info': info},
    ErrorMessages.E_POOL_DETACH : lambda info: _("Error while detaching the disk array: %(info)s") % {'info': info},
    ErrorMessages.E_POOL_MOUNT : lambda info: _("Error while mounting the disk array: %(info)s") % {'info': info},
    ErrorMessages.E_POOL_UNMOUNT : lambda info: _("Error while unmounting the disk array: %(info)s") % {'info': info},
    ErrorMessages.E_POOL_MOUNTED : lambda: _("Disk array is mounted."),
    ErrorMessages.E_POOL_UNMOUNTED : lambda: _("Disk array is unmounted."),
    ErrorMessages.E_POOL_SCRUB : lambda info : _("Error while verifying the disk array: %(info)s.") % {'info',info},
    ErrorMessages.E_POOL_INVALID_MOUNTPOINT : lambda: _("The provided mount point is not valid.") ,
    ErrorMessages.E_POOL_MOUNT_STATUS : lambda info: _("Error while retrieving the mount information the disk array: %(info)s") % {
        'info': info},

    ErrorMessages.E_POOL_MOUNTPOINT : lambda info: _("Error while retrieving the mount point: %(info)s") % {'info': info},
    ErrorMessages.E_POOL_RM_MOUNTPOINT : lambda info: _("Error while removing the mount point: %(info)s") % {'info': info},
    ErrorMessages.E_POOL_FORMAT : lambda info: _("Error while formatting the disk array: %(info)s") % {'info': info},
    ErrorMessages.E_POOL_CAPACITY : lambda info = None: _("Unable to read disk array capacity information: %(info)s") % {
        'info': info or ErrorMessages.fallback_message()},

    ErrorMessages.E_POOL_OPENED : lambda : _("One or more disks cannot be opened. Your disk array CANNOT be used in this state. Run a diagnostic to see if the disk is getting faulted and replace if necessary. Alternatively, you can format it in the Advanced page (this can likely cause data loss)."),
    ErrorMessages.E_POOL_DISK_MISSING: lambda : _("One or more disks seems missing. Your disk array CANNOT be used in this state. Insert back the missing disk. If the disk is inserted and still see this error, you can format it in the Advanced page (this can likely cause data loss)."),
    ErrorMessages.E_POOL_CORRUPTED: lambda : _("The information related your disk array are corrupted. Recovery may be possible (but not guaranteed) and some data loss can occur. Use the `Attempt Recovery` button in Advanced. If the problem persists, back up your data, destroy and create a new array. Consider replacing one or more disks if their diagnostics suggest so."),
    ErrorMessages.E_POOL_OUTDATED: lambda : _("Your disk array seems to be outdated and cannot be used anymore."),
    ErrorMessages.E_POOL_SNAPSHOT_NAME: lambda name: _("Snapshot name `%(name)s` is invalid.") % {"name":name},
    ErrorMessages.E_POOL_SNAPSHOT_CREATE: lambda info: _("Error while creating a new snapshot of your disk array: %(info)s") % {'info':info},
    ErrorMessages.E_POOL_SNAPSHOT_DELETE: lambda name,info: _("Error while deleting the snapshot `%(name)s` from your disk array: %(info)s") % {'info':info,'name':name},
    ErrorMessages.E_POOL_SNAPSHOTS: lambda info: _("Error while retrieving the list of snapshots: %(info)s") % {'info':info},
    ErrorMessages.E_POOL_SNAPSHOT_ROLLBACK: lambda name,info: _("Error while rolling back to `%(name)s`: %(info)s") % {'info':info, 'name':name},

    ErrorMessages.E_AUTH_ALREADY_CONFIG : lambda : _("You have already an OTP credentials configured."),
    ErrorMessages.E_AUTH_INVALID : lambda: _("Invalid authorisation."),
    ErrorMessages.E_AUTH_EXPIRED : lambda: _("Authorisation token expired."),
    ErrorMessages.E_AUTH_REVOKED : lambda: _("Authorisation token revoked."),
    ErrorMessages.E_AUTH_MALFORMED : lambda: _("Authorisation token malformed."),
    ErrorMessages.E_AUTH_NOT_CONF : lambda: _("OTP secret not configured yet."),
    ErrorMessages.E_AUTH_WRONG_OTP : lambda: _("Invalid OTP."),

    ErrorMessages.E_DISK_ATTACH : lambda details: _("Unable to attach new device to disk array: %(details)s") % {'details': details},
    ErrorMessages.E_DISK_FORMAT : lambda dev, info: _("Error while formatting %(dev)s: %(info)s") % {'dev': dev, 'info': info},
    ErrorMessages.E_DISK_SELF_TEST: lambda dev, info: _("Error while running a self-test on %(dev)s: %(info)s") % {'dev': dev, 'info': info},

    ErrorMessages.E_FS_CH_PERM : lambda path, info: _("Unable to change permissions for %(path)s: %(info)s") % {'path':path,'info': info},

    ErrorMessages.E_APT_GET : lambda info = None: _("Unable to get system updates: %(info)s") % {'info': info or ErrorMessages.fallback_message()},
    ErrorMessages.E_APT_UNK : lambda : _("Unable to update your current system. You may do so manually by accessing it via SSH."),

    ErrorMessages.E_ACCESS_ENABLED : lambda service,info: _("Error while enabling %(service)s: %(info)s") % {'service':service,'info': info},
    ErrorMessages.E_ACCESS_DISABLED : lambda service,info: _("Error while disabling %(service)s: %(info)s") % {'service':service,'info': info},
    ErrorMessages.E_ACCESS_DISABLING : lambda service,info: _("Unable to disable %(service)s. Please, disable it manually.") % {'service':service},
    ErrorMessages.E_ACCESS_SERV_UNK: lambda service: _("Access service %(service)s not recognised.") % {'service':service},
    ErrorMessages.E_ACCESS_PROP: lambda prop,info: _("Error while changing the property `%(prop)s`: %(info)s") % {'prop':prop,'info':info},

    ErrorMessages.E_NET_CHANGE_STATE : lambda iface,info : _("Error while changing the state of the network interface %(iface)s: %(info)s") % {'info':info,'iface':iface},
    ErrorMessages.E_NET_CONNECTION_STATUS : lambda iface,info : _("Error while retrieving the connection status for %(iface)s: %(info)s") % {'info':info,'iface':iface},
    ErrorMessages.E_NET_INVALID_NETMASK : lambda : _("Invalid subnet mask"),
    ErrorMessages.E_NET_INVALID_IP_ADDRESS : lambda : _("Invalid IP address "),
    ErrorMessages.E_NET_INVALID_GATEWAY : lambda : _("Invalid gateway"),
    ErrorMessages.E_NET_INVALID_DNS : lambda : _("Invalid DNS address(es)"),
    ErrorMessages.E_NET_WIFI_LIST : lambda iface,info: _("Error while retrieving the list of WiFi networks for %(iface)s: %(info)s") % {"iface":iface,"info":info},
    ErrorMessages.E_NET_WIFI_CONNECT : lambda ssid,info: _("Unable to connect to `%(ssid)s`: %(info)s") % {'info':info,'ssid':ssid},
    ErrorMessages.E_NET_WIFI_DEV : lambda : _("No valid WiFi network interfaces detected."),
    ErrorMessages.E_NET_AP : lambda iface,info : _("Unable to create hotspot on %(iface)s: %(info)s") % {'iface':iface,'info':info},
    ErrorMessages.E_NET_VPN_NOTCONF : lambda : _("VPN service not configured."),
    ErrorMessages.E_NET_VPN_STATE : lambda info: _("Unable to get the state of the VPN service: %(info)s") % {'info':info},
    ErrorMessages.E_NET_VPN_KEY : lambda info = None: _("Error while retrieving the VPN key: %(info)s") % {'info': info or ErrorMessages.fallback_message()},
    ErrorMessages.E_NET_VPN_GEN_PRIVATE : lambda info: _("Error occurred while generating the private key: %(info)s") % {'info':info},
    ErrorMessages.E_NET_VPN_GEN_PUBLIC : lambda info: _("Error occurred while generating the public key: %(info)s") % {'info':info},
    ErrorMessages.E_NET_VPN_CONF : lambda info: _("Error occurred while reading the VPN configuration file: %(info)s") % {'info':info},
    ErrorMessages.E_NET_VPN_USER : lambda user: _("VPN device `%(user)s` not found.") % {'user':user},
    ErrorMessages.E_NET_VPN_USER_INVALID : lambda : _("VPN device not valid."),
    ErrorMessages.E_NET_VPN_IP_MAX : lambda : _("You have reached the maximum number of devices."),
    ErrorMessages.E_NET_DDNS_INVALID : lambda provider : _("Invalid dynamic DNS provider `%(provider)`.") % {'provider':provider},
    ErrorMessages.E_NET_DDNS_SERVICE : lambda provider,info : _("Error occurred during the execution of the dynamic DNS provider `%(provider)s`: %(info)s") % {'provider':provider,"info":info},
    ErrorMessages.E_NET_DDNS_CONFIG : lambda : _("Missing Dynamic DNS configuration. Check if username/domain and password/token are properly set for the chosen provider."),

    ErrorMessages.E_USER_NOT_FOUND : lambda user : _("User %(user)s not found.") % {'user':user},
    ErrorMessages.E_USER_PASSWD : lambda user : _("Unable to change the password for %(user)s.") % {'user':user},
    ErrorMessages.E_USER_QUOTA : lambda info: _("Error occurred while setting the user quota: %(info)s.") % {'info':info}, #<-----
    ErrorMessages.E_USER_NAME: lambda info: _("Error occurred while changing username: %(info)s.") % {'info':info}, #<-----
    ErrorMessages.E_USER_SUDO: lambda info : _("Unable to change user's system privileges: %(info)s") % {'info':info}, #<-----
    ErrorMessages.E_NEW_USER: lambda info: _("Error occurred while creating a new user: %(info)s.") % {'info':info}, #<-----
    ErrorMessages.E_PERM_ADMIN : lambda : _("Permission changes are disabled because this is the only administrator account. "
                                            "At least one additional administrator must exist to prevent lockout. "
                                            "Users with all permissions are treated as administrators."),
    ErrorMessages.E_DEL_ADMIN : lambda : _("You cannot delete this account because this is the only administrator account. "
                                            "At least one additional administrator must exist to prevent lockout. "
                                            "Users with all permissions are treated as administrators."),
    ErrorMessages.E_USER_COPY_FILES: lambda user,info: _("Error occurred while moving files of the user %(user)s: %(info)s.") % {'info':info,'user':user}, #<-----
    ErrorMessages.E_USER_DELETE: lambda user,info: _("Error occurred while deleting the user %(user)s: %(info)s.") % {'info':info,'user':user}, #<-----
    ErrorMessages.E_USER_LOGIN_RESET : lambda user,info: _("Error occurred while resetting the login credentials for %(user)s: %(info)s.") % {'info':info,'user':user}, #<-----
    ErrorMessages.E_USER_SYSTEM: lambda info: _("Error while retrieving the list of system users: %(info)s.") % {'info':info},

    ErrorMessages.E_SYSTEM_UPDATES: lambda: _("Unable to retrieve updates."),
    ErrorMessages.E_SYSTEM_DIST: lambda info: _("Error while creating distribution archive: %(info)s.") % {'info':info},

    ErrorMessages.E_FS_NOT_FILE: lambda path: _("The provided path `%(path)s` neither exists nor is a file.") % {'path':path},
    ErrorMessages.E_FS_ZIP: lambda path,info: _("Error while zipping: `%(path)s`: %(info)s.") % {'path':path,'info':info},
    ErrorMessages.E_FS_UNZIP: lambda path,info: _("Error while unzipping: `%(path)s`: %(info)s.") % {'path':path,'info':info},
    ErrorMessages.E_FS_COPY: lambda path,info: _("Error while copying: `%(path)s`: %(info)s.") % {'path':path,'info':info},
    ErrorMessages.E_FS_MOVE: lambda path,info: _("Error while moving: `%(path)s`: %(info)s.") % {'path':path,'info':info},
    ErrorMessages.E_FS_MKDIR: lambda path,info: _("Error while creating the directory `%(path)s`: %(info)s.") % {'path':path,'info':info},

    ErrorMessages.E_EVENT_INVALID_ACTION : lambda action, event : _("The action `%(action)s` cannot be used for the event `%(event)s`") % {'action':action,'event':event},
    ErrorMessages.E_EVENT_INVALID_PARAM : lambda  parameter, action : _("Invalid parameter for the action `%(action)s`: %(parameter)s.") % {'action':action,'parameter':parameter},
    ErrorMessages.E_EVENT_INVALID : lambda : _("Invalid event"),
    ErrorMessages.E_ACTION_INVALID : lambda : _("Invalid action"),

}

WARNING_MESSAGES = {
    WarningMessages.W_POOL_OPENED  : lambda : _("One or more disks cannot be opened. As you have redundancy activated, you can still use your disk array. Run a diagnostic to see if the disk is getting faulted and replace if necessary. Alternatively, you can format it in the Advanced page."),
    WarningMessages.W_POOL_MISSING : lambda : _("One or more disks seems missing. As you have redundancy activated, you can still use your disk array. Insert back the missing disk. If the disk is inserted and still see this error, press `Replace` in the Disk Management page."),
    WarningMessages.W_POOL_CORRUPTED : lambda : _("Some files and/or directories are corrupted and data cannot be recovered. If the problem persists, back up your data, destroy and create a new array. Consider replacing one or more disks if their diagnostics suggest so."),
    WarningMessages.W_DISK_ISSUE : lambda : _("One or more disks appear to experience some problems. No imminent actions are required at the moment. However, you should investigate which disk(s) is getting old and consider replacing it."),
    WarningMessages.W_DISK_FORMAT : lambda : _("Your disk array is experiencing some format issues. To solve this issue, press `Verify` in the Disk Management page."),
    WarningMessages.W_POOL_NEEDED : lambda : _("You need to configure your disk array before enabling any access services"),
    WarningMessages.W_POOL_DISK_OFFLINE : lambda : _("One or more of your disks in the array is offline. If redundancy is active, you can still use the array. Please, reinsert or replace your disk soon."),
    WarningMessages.W_NEW_USER : lambda user, info : _("User %(user)s has been created successfully. However, there has been some issues in setting their quota: %(info)s.") % {'user':user,"info":info},
    WarningMessages.W_USER_NO_UID: lambda: _("Your user does not have a local user associated. Contact a system administrator to fix the issue in the Users tab.")
}

SUCCESS_MESSAGES = {
    SuccessMessages.S_POOL_CREATED : lambda: _("Disk array created successfully."),
    SuccessMessages.S_POOL_EXPANDED : lambda: _("Disk array expanded successfully."),
    SuccessMessages.S_POOL_FORMATTED : lambda: _("Disk array formatted successfully."),
    SuccessMessages.S_POOL_DESTROYED : lambda: _("Disk array destroyed successfully."),
    SuccessMessages.S_POOL_MOUNTED : lambda: _("Disk array mounted successfully."),
    SuccessMessages.S_POOL_UNMOUNTED : lambda: _("Disk array unmounted successfully."),
    SuccessMessages.S_POOL_SCRUB : lambda: _("Disk array verification performed successfully."),
    SuccessMessages.S_POOL_REPLACE_DISK : lambda: _("Disk replaced successfully."),
    SuccessMessages.S_POOL_SNAPSHOT_CREATE: lambda : _("Snapshot created successfully"),
    SuccessMessages.S_POOL_SNAPSHOT_DELETE: lambda : _("Snapshot deleted successfully"),
    SuccessMessages.S_POOL_SNAPSHOT_ROLLBACK: lambda name : _("Disk array rolled back to `%(name)s`.") % {'name':name},

    SuccessMessages.S_APT_UPDATE : lambda: _("System updates retrieved successfully."),
    SuccessMessages.S_APT_UPGRADE : lambda: _("System updates installed successfully."),

    SuccessMessages.S_OTP_DANGEROUS : lambda: _("OTP Accepted. Please press again the button of the desired dangerous operation to continue."),

    SuccessMessages.S_RECOVERY : lambda: _("Disk array recovery attempted."),

    SuccessMessages.S_ACCESS_ENABLED : lambda service : _("Service %(service)s enabled successfully.") % {'service':service},
    SuccessMessages.S_ACCESS_UPDATED : lambda service : _("Service %(service)s settings updated successfully.") % {'service':service},
    SuccessMessages.S_ACCESS_DISABLED : lambda service : _("Service %(service)s disabled successfully.") % {'service':service},

    SuccessMessages.S_DISK_FORMATTED : lambda dev : _("Disk %(dev)s formatted successfully.") % {'dev':dev},
    SuccessMessages.S_DISK_SELF_TEST : lambda dev : _("Disk self-test launched successfully on %(dev)s. Check the logs below to track the progression status and results.") % {'dev':dev},

    SuccessMessages.S_NET_VPN_KEYSGEN : lambda : _("VPN private and public keys generated successfully.") ,
    SuccessMessages.S_NET_VPN_CONFIG : lambda : _("VPN configuration changes applied successfully.") ,
    SuccessMessages.S_NET_CONFIG : lambda iface: _("Network configuration changes for %(iface)s applied successfully.") % {'iface':iface} ,
    SuccessMessages.S_NET_VPN_PEER_DELETED : lambda peer: _("Device `%(peer)s` deleted successfully.") % {'peer':peer} ,
    SuccessMessages.S_NET_VPN_PEER_ADDED : lambda peer: _("Device `%(peer)s` added successfully.") % {'peer':peer} ,
    SuccessMessages.S_NET_DDNS_ENABLED : lambda provider: _("Dynamic DNS provider `%(provider)s` enabled successfully.") % {'provider':provider} ,
    SuccessMessages.S_NET_DDNS_DISABLED : lambda provider: _("Dynamic DNS provider `%(provider)s` disabled successfully.") % {'provider':provider},
    SuccessMessages.S_NET_AP : lambda iface,ssid : _("The wifi interface %(iface)s is now a hotspot with the SSID %(ssid)s.") % {'iface':iface,'ssid':ssid},

    SuccessMessages.S_USER_PASSWORD : lambda : _("Password changed successfully."),
    SuccessMessages.S_USER_FULLNAME : lambda : _("Visible name changed successfully."),
    SuccessMessages.S_USER_QUOTA : lambda : _("User quota set successfully."),
    SuccessMessages.S_USER_NAME : lambda : _("Username changed successfully."),
    SuccessMessages.S_USER_SUDO : lambda : _("User's system privileges changed successfully."),
    SuccessMessages.S_NEW_USER : lambda user : _("User %(user)s created successfully.") % {'user':user} ,
    SuccessMessages.S_DEL_USER: lambda user: _("User %(user)s deleted successfully.") % {'user': user},
    SuccessMessages.S_USER_PERM : lambda : _("Permissions changed successfully."),
    SuccessMessages.S_USER_LOGIN_RESET: lambda user : _("User login reset successfully. Provide to the user %(user)s the new first-time login link to set new credentials.") % {'user':user},
    SuccessMessages.S_EVENT_ADDED: lambda : _("Event  added successfully."),
    SuccessMessages.S_EVENT_ENABLED : lambda uuid : _("Event %(uuid)s enabled successfully.") % {'uuid':uuid},
    SuccessMessages.S_EVENT_DISABLED : lambda uuid : _("Event %(uuid)s disabled successfully.") % {'uuid':uuid},
    SuccessMessages.S_EVENT_DELETED : lambda uuid : _("Event %(uuid)s deleted successfully.") % {'uuid':uuid},
    SuccessMessages.S_EVENT_UPDATED : lambda uuid : _("Event %(uuid)s updated successfully.") % {'uuid':uuid},
}

INFO_MESSAGES = {
    InfoMessages.I_POOL_EXPANSION_ETA : lambda eta: _("Disk expansion is expected to take %(eta)s.") % {'eta':eta},
    InfoMessages.I_POOL_EXPANSION : lambda: _("Disk expansion in progress."),
    InfoMessages.I_POOL_DISK_REPLACEMENT : lambda: _("Disk replacement in progress. This operation may take a while.")
}

EVENT_NAMES = {
    EventNames.SYSTEM : lambda : _("System events"),
    EventNames.SYSTEM_STARTUP: lambda : _("When the system starts up"),
    EventNames.SYSTEM_REBOOT: lambda : _("When the system is rebooted"),
    EventNames.SYSTEM_POWEROFF: lambda : _("When the system is powering off"),
    EventNames.SYSTEM_SHUTDOWN: lambda : _("When the system is shutting down (either rebooting or powering off)"),
    EventNames.SYSTEM_SYSTEMD: lambda : _("When the system services are restarted"),
    EventNames.SYSTEM_UPDATES: lambda : _("When new system updates are available"),
    EventNames.SYSTEM_UPGRADE: lambda : _("When the system has been upgraded"),

    EventNames.DISK: lambda : _("Disk-related events"),
    EventNames.DISK_MOUNT : lambda  : _("When the disk array is mounted"),
    EventNames.DISK_UNMOUNT : lambda  : _("When the disk array is unmounted"),

    EventNames.USER : lambda : _("User events"),
    EventNames.USER_LOGGED_IN : lambda : _("When a user logs in"),
    EventNames.USER_CREATED: lambda : _("When a user is created"),
    EventNames.USER_DELETED: lambda : _("When a user is deleted"),


    EventNames.ACCESS : lambda : _("Remote access services events"),
    EventNames.ACCESS_ENABLED : lambda : _("When an access service is enabled"),
    EventNames.ACCESS_DISABLED : lambda : _("When an access service is disabled"),

    EventNames.NETWORK : lambda : _("Network events"),
    EventNames.VPN_ENABLED : lambda : _("When the VPN is enabled"),
    EventNames.VPN_DISABLED : lambda : _("When the VPN is disabled"),

    EventNames.TIMER : lambda : _("Timed events"),
    EventNames.TIMER_MINUTES : lambda : _("At every specified time interval"),

    EventNames.FILE: lambda : _("File events"),
    EventNames.FILE_CREATED: lambda : _("When a file is created"),
    EventNames.FILE_DELETED: lambda : _("When a file is deleted"),
    EventNames.FILE_MODIFIED: lambda : _("When a file is modified"),

}

ACTION_CATEGORIES = {
    "notification": lambda : _("Send a notification to..."),
    "execution": lambda : _("Run..."),
    "file": lambda : _("File management"),
}

ACTION_NAMES = {
    "send_to": lambda : _("A specific user"),
    "send_to_all": lambda : _("All users"),
    "send_to_admins": lambda : _("All admins"),
    "run_script": lambda : _("A custom program or script"),
    "change_owner" : lambda : _("Change Owner"),
    "change_permissions" : lambda : _("Change Permissions")

}

PARAMS_NAMES = {
    "user": lambda : _("Username"),
    "subject": lambda : _("Subject"),
    "message": lambda : _("Message"),
    "path": lambda : _("Path"),
    "run_sudo": lambda : _("Run as sudo"),
    "minutes": lambda : _("Time (minutes)"),
    "group": lambda : _("Group"),
    "permissions": lambda : _("Permissions"),
}

CONTEXT_VARS = {
    "TRIGGER_USER": lambda : _("The username who triggered the event"),
    "USER" : lambda : _("Recipient Username"),
    "ACCOUNT" : lambda : _("Created/Deleted Username"),
    "ISO_TIMESTAMP": lambda : _("Date and time in ISO format"),
    "PACKAGES": lambda : _("Comma-separated list of packages"),
    "SERVICE": lambda : _("Enabled/Disabled access service"),
    "PATH" : lambda : _("Path"),
    "FILENAME" : lambda : _("File name"),
    "ISDIR" : lambda : _("Is directory"),
    "HOME_OWNER" : lambda : _("User owning the home directory"),
    "PERMISSIONS" : lambda : _("Permissions"),
    "GROUP" : lambda : _("Group"),
}