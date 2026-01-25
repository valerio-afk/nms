from enum import Enum
from typing import Callable,List, Any
from flask_babel import _

def parse_msg(msg:Callable[...,str],*args,**kwargs) -> str:
    return str(msg(*args,**kwargs))


class ErrorMessages(Enum):
    E_UNKNOWN = "E_UNKNOWN"
    E_PROPERTY = "E_PROPERTY"

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
    E_POOL_ATTACH = "E_POOL_DETACH"
    E_POOL_DETACH = "E_POOL_DETACH"
    E_POOL_MOUNT = "E_POOL_MOUNT"
    E_POOL_UNMOUNT = "E_POOL_UNMOUNT"
    E_POOL_MOUNTED = "E_POOL_MOUNTED"
    E_POOL_UNMOUNTED = "E_POOL_UNMOUNTED"
    E_POOL_RM_MOUNTPOINT = "E_POOL_RM_MOUNTPOINT"
    E_POOL_INVALID_MOUNTPOINT = "E_POOL_INVALID_MOUNTPOINT"
    E_POOL_MOUNT_STATUS = "E_POOL_MOUNT_STATUS"
    E_POOL_MOUNTPOINT = "E_POOL_MOUNTPOINT"
    E_POOL_FORMAT = "E_POOL_FORMAT"
    E_POOL_CAPACITY = "E_POOL_CAPACITY"

    E_AUTH_INVALID = "E_AUTH_INVALID"
    E_AUTH_EXPIRED = "E_AUTH_EXPIRED"
    E_AUTH_MALFORMED = "E_AUTH_MALFORMED"
    E_AUTH_NOT_CONF = "E_AUTH_NOT_CONF"
    E_AUTH_WRONG_OTP = "E_AUTH_WRONG_OTP"

    E_DISK_ATTACH = "E_DISK_ATTACH"
    E_DISK_FORMAT = "E_DISK_FORMAT"

    E_FS_CH_PERM =  "E_FS_CH_PERM"

    @staticmethod
    def get_error(err_code:"ErrorMessage",*args,**kwargs) -> str:
        return parse_msg(ERROR_MESSAGES[err_code],*args,**kwargs)

    @staticmethod
    def fallback_message():
        return ErrorMessages.get_error(ErrorMessages.E_UNKNOWN)

class SuccessMessages(Enum):
    S_POOL_CREATED = "S_POOL_CREATED"
    S_POOL_EXPANDED = "S_POOL_EXPANDED"

    S_APT_UPDATE = "S_APT_UPDATE"
    S_APT_UPGRADE = "S_APT_UPGRADE"

    S_OTP_DANGEROUS = "S_OTP_DANGEROUS"

    S_RECOVERY = "S_RECOVERY"

    @staticmethod
    def get_message(success_code:"SuccessMessage",*args,**kwargs) -> str:
        return parse_msg(SUCCESS_MESSAGES[success_code],*args,**kwargs)


ERROR_MESSAGES = {
    ErrorMessages.E_UNKNOWN : lambda: _("Unknown Error"),
    ErrorMessages.E_PROPERTY : lambda prop, info: _("Error while getting %(prop)s: %(info)s") % {'prop': prop, 'info': info}, # <------

    ErrorMessages.E_POOL_ALREADY_CONF : lambda: _("The disk array is already configured."),
    ErrorMessages.E_POOL_NO_CONF : lambda: _("Disk array not configured yet."),
    ErrorMessages.E_POOL_CONFIG : lambda: _("Disk array is configured."), # <------
    ErrorMessages.E_POOL_DISK_UNAVAL : lambda dev : _("Disk %(dev)s is not available to be in the new disk array.") % {'dev':dev}, # <------
    ErrorMessages.E_POOL_NEW : lambda info = None: _("Unable to create a new disk array: %(info)s)") % {
        'info': info or ErrorMessages.fallback_message()},  # <------
    ErrorMessages.E_POOL_DESTROY : lambda info = None: _("Unable to destroy the disk array: %(info)s)") % {
        'info': info or ErrorMessages.fallback_message()},  # <------
    ErrorMessages.E_POOL_REDUNDANCY_MIN : lambda: _("You must have at least 3 disks connected to opt in redundancy."),
    ErrorMessages.E_POOL_EXPAND : lambda dev, info: _("Error while adding %(dev)s: %(info)s") % {'dev': dev, 'info': info},
    ErrorMessages.E_POOL_EXPAND_INFO : lambda dev: _("Could not retrieve information for the disk: %(dev)s") % {'dev': dev},
    ErrorMessages.E_POOL_EXPAND_STATUS : lambda info: _("Unable to get array expansion status: %(info)s") % {'info': info},
    ErrorMessages.E_POOL_KEY : lambda info: _("Error while retrieving the encryption key: %(info)s") % {'info': info}, # <------
    ErrorMessages.E_POOL_KEY_IMPORT : lambda info: _("Error while importing the encryption key: %(info)s") % {'info': info}, # <------
    ErrorMessages.E_POOL_ATTACH : lambda info: _("Error while attaching an existing pool: %(info)s") % {'info': info}, # <------
    ErrorMessages.E_POOL_LIST : lambda info: _("Unable to retrieve the list of pools."), # <------
    ErrorMessages.E_POOL_RECOVERY : lambda info: _("Error while recovering the disk array: %(info)s)") % {'info': info},
    ErrorMessages.E_POOL_DISKS : lambda info: _("Error while retrieving the disks in the array: %(info)s)") % {'info': info},  # <------
    ErrorMessages.E_POOL_DETACH : lambda info: _("Error while detaching the disk array: %(info)s)") % {'info': info},  # <------
    ErrorMessages.E_POOL_MOUNT : lambda info: _("Error while mounting the disk array: %(info)s)") % {'info': info},  # <------
    ErrorMessages.E_POOL_UNMOUNT : lambda info: _("Error while unmounting the disk array: %(info)s)") % {'info': info}, # <------
    ErrorMessages.E_POOL_MOUNTED : lambda: _("Disk array is mounted."),  # <------
    ErrorMessages.E_POOL_UNMOUNTED : lambda: _("Disk array is unmounted."),  # <------
    ErrorMessages.E_POOL_INVALID_MOUNTPOINT : lambda: _("The provided mount point is not valid.") , # <------
    ErrorMessages.E_POOL_MOUNT_STATUS : lambda info: _("Error while retrieving the mount information the disk array: %(info)s)") % {
        'info': info},  # <------
    ErrorMessages.E_POOL_MOUNTPOINT : lambda info: _("Error while retrieving the mount point: %(info)s)") % {'info': info},  # <------
    ErrorMessages.E_POOL_RM_MOUNTPOINT : lambda info: _("Error while removing the mount point: %(info)s)") % {'info': info},  # <------
    ErrorMessages.E_POOL_FORMAT : lambda info: _("Error while formatting the disk array: %(info)s)") % {'info': info},  # <------
    ErrorMessages.E_POOL_CAPACITY : lambda info = None: _("Unable to read disk array capacity information: %(info)s)") % {
        'info': info or ErrorMessages.fallback_message()},  # <------

    ErrorMessages.E_AUTH_INVALID : lambda: _("Invalid authorisation."),
    ErrorMessages.E_AUTH_EXPIRED : lambda: _("Authorisation token expired."),
    ErrorMessages.E_AUTH_MALFORMED : lambda: _("Authorisation token malformed."),  # <------
    ErrorMessages.E_AUTH_NOT_CONF : lambda: _("OTP secret not configured yet."),  # <------
    ErrorMessages.E_AUTH_WRONG_OTP : lambda: _("Invalid OTP."),  # <------

    ErrorMessages.E_DISK_ATTACH : lambda details: _("Unable to attach new device to disk array%(details)s") % {'details': details}, # <------
    ErrorMessages.E_DISK_FORMAT : lambda dev, info: _("Error while formatting %(dev)s: %(info)s") % {'dev': dev, 'info': info},

    ErrorMessages.E_FS_CH_PERM : lambda path, info: _("Unable to change permissions for %(path)s: %(info)s") % {'path':path,'info': info}, # <------
}

SUCCESS_MESSAGES = {
    SuccessMessages.S_POOL_CREATED : lambda: _("Disk array created successfully."),
    SuccessMessages.S_POOL_EXPANDED : lambda: _("Disk array expanded successfully."),

    SuccessMessages.S_APT_UPDATE : lambda: _("System updates retrieved successfully."),
    SuccessMessages.S_APT_UPGRADE : lambda: _("System updates installed successfully."),

    SuccessMessages.S_OTP_DANGEROUS : lambda: _("OTP Accepted. Please press again the button of the desired dangerous operation to continue."),

    SuccessMessages.S_RECOVERY : lambda: _("Disk array recovery attempted."),
}