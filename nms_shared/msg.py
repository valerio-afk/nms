from enum import Enum
from flask_babel import _
from typing import Callable

def parse_msg(msg:Callable[...,str],*args,**kwargs) -> str:
    return str(msg(*args,**kwargs))


class ErrorMessages(Enum):
    E_UNKNOWN = "E_UNKNOWN"
    E_UNKNOWN_RESPONSE = "E_UNKNOWN_RESPONSE"
    E_PROPERTY = "E_PROPERTY"
    E_CSRF = "E_CSRF"

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

    E_AUTH_INVALID = "E_AUTH_INVALID"
    E_AUTH_EXPIRED = "E_AUTH_EXPIRED"
    E_AUTH_REVOKED = "E_AUTH_REVOKED"
    E_AUTH_MALFORMED = "E_AUTH_MALFORMED"
    E_AUTH_NOT_CONF = "E_AUTH_NOT_CONF"
    E_AUTH_WRONG_OTP = "E_AUTH_WRONG_OTP"

    E_DISK_ATTACH = "E_DISK_ATTACH"
    E_DISK_FORMAT = "E_DISK_FORMAT"

    E_FS_CH_PERM =  "E_FS_CH_PERM"

    E_APT_GET = "E_APT_GET"

    E_ACCESS_ENABLED = "E_ACCESS_ENABLED"
    E_ACCESS_DISABLED = "E_ACCESS_DISABLED"
    E_ACCESS_DISABLING = "E_ACCESS_DISABLING"
    E_ACCESS_SERV_UNK = "E_ACCESS_SERV_UNK"

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
    W_DISK_ISSUE = "W_DISK_ISSUE"
    W_DISK_FORMAT = "W_DISK_FORMAT"

    @staticmethod
    def get_warning(warn_code: "WarningMessages", *args, **kwargs) -> str:
        return parse_msg(ERROR_MESSAGES[warn_code], *args, **kwargs)

class SuccessMessages(Enum):
    S_POOL_CREATED = "S_POOL_CREATED"
    S_POOL_EXPANDED = "S_POOL_EXPANDED"
    S_POOL_FORMATTED = "S_POOL_FORMATTED"
    S_POOL_DESTROYED = "S_POOL_DESTROYED"

    S_APT_UPDATE = "S_APT_UPDATE"
    S_APT_UPGRADE = "S_APT_UPGRADE"

    S_OTP_DANGEROUS = "S_OTP_DANGEROUS"

    S_RECOVERY = "S_RECOVERY"

    S_ACCESS_ENABLED = "S_ACCESS_ENABLED"
    S_ACCESS_UPDATED = "S_ACCESS_UPDATED"
    S_ACCESS_DISABLED = "S_ACCESS_DISABLED"

    S_DISK_FORMATTED = "S_DISK_FORMATTED"

    @staticmethod
    def get_message(success_code:"SuccessMessage",*args,**kwargs) -> str:
        return parse_msg(SUCCESS_MESSAGES[success_code],*args,**kwargs)

    @staticmethod
    def get_success_from_string(code:str,*args,**kwargs) -> str:
        return SuccessMessages.get_message(SuccessMessages[code],*args,**kwargs)


ERROR_MESSAGES = {
    ErrorMessages.E_UNKNOWN : lambda: _("Unknown Error"),
    ErrorMessages.E_UNKNOWN_RESPONSE : lambda: _("Unknown response from server"), # <------
    ErrorMessages.E_PROPERTY : lambda prop, info: _("Error while getting %(prop)s: %(info)s") % {'prop': prop, 'info': info}, # <------
    ErrorMessages.E_CSRF : lambda : _("Form validation failed"), # <------

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
    ErrorMessages.E_POOL_DISK_REPLACE : lambda d1,d2,info: _("Unable to replace %(dev1)s with %(dev2)s: %(info)s") % {'dev1':d1, 'dev2': d2, 'info': info}, # <------
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

    ErrorMessages.E_POOL_OPENED : lambda : _("One or more disks cannot be opened. Your disk array CANNOT be used in this state. Run a diagnostic to see if the disk is getting faulted and replace if necessary. Alternatively, you can format it in the Advanced page (this can likely cause data loss)."), # <-----------
    ErrorMessages.E_POOL_DISK_MISSING: lambda : _("One or more disks seems missing. Your disk array CANNOT be used in this state. Insert back the missing disk. If the disk is inserted and still see this error, you can format it in the Advanced page (this can likely cause data loss)."), # <-----------
    ErrorMessages.E_POOL_CORRUPTED: lambda : _("The information related your disk array are corrupted. Recovery may be possible (but not guaranteed) and some data loss can occur. Use the `Attempt Recovery` button in Advanced. If the problem persists, back up your data, destroy and create a new array. Consider replacing one or more disks if their diagnostics suggest so."), # <-----------
    ErrorMessages.E_POOL_OUTDATED: lambda : _("Your disk array seems to be outdated and cannot be used anymore."), # <-----------

    ErrorMessages.E_AUTH_INVALID : lambda: _("Invalid authorisation."),
    ErrorMessages.E_AUTH_EXPIRED : lambda: _("Authorisation token expired."),
    ErrorMessages.E_AUTH_REVOKED : lambda: _("Authorisation token revoked."),  # <------
    ErrorMessages.E_AUTH_MALFORMED : lambda: _("Authorisation token malformed."),  # <------
    ErrorMessages.E_AUTH_NOT_CONF : lambda: _("OTP secret not configured yet."),  # <------
    ErrorMessages.E_AUTH_WRONG_OTP : lambda: _("Invalid OTP."),  # <------

    ErrorMessages.E_DISK_ATTACH : lambda details: _("Unable to attach new device to disk array%(details)s") % {'details': details}, # <------
    ErrorMessages.E_DISK_FORMAT : lambda dev, info: _("Error while formatting %(dev)s: %(info)s") % {'dev': dev, 'info': info},

    ErrorMessages.E_FS_CH_PERM : lambda path, info: _("Unable to change permissions for %(path)s: %(info)s") % {'path':path,'info': info}, # <------

    ErrorMessages.E_APT_GET : lambda info: _("Unable to get system updates: %(info)s") % {'info': info or ErrorMessages.fallback_message()}, # <------

    ErrorMessages.E_ACCESS_ENABLED : lambda service,info: _("Error while enabling %(service)s: %(info)s)") % {'service':service,'info': info},  # <------
    ErrorMessages.E_ACCESS_DISABLED : lambda service,info: _("Error while disabling %(service)s: %(info)s)") % {'service':service,'info': info},  # <------
    ErrorMessages.E_ACCESS_DISABLING : lambda service,info: _("Unable to disable %(service)s. Please, disable it manually.") % {'service':service},  # <------
    ErrorMessages.E_ACCESS_SERV_UNK: lambda service: _("Access service %(service)s not recognised.") % {'service':service}, # <------
}

WARNING_MESSAGES = {
    WarningMessages.W_POOL_OPENED  : lambda : _("One or more disks cannot be opened. As you have redundancy activated, you can still use your disk array. Run a diagnostic to see if the disk is getting faulted and replace if necessary. Alternatively, you can format it in the Advanced page."),
    WarningMessages.W_POOL_MISSING : lambda : _("One or more disks seems missing. As you have redundancy activated, you can still use your disk array. Insert back the missing disk. If the disk is inserted and still see this error, press `Replace` in the Disk Management page."),
    WarningMessages.W_POOL_CORRUPTED : lambda : _("Some files and/or directories are corrupted and data cannot be recovered. If the problem persists, back up your data, destroy and create a new array. Consider replacing one or more disks if their diagnostics suggest so."),
    WarningMessages.W_DISK_ISSUE : lambda : _("One or more disks appear to experience some problems. No imminent actions are required at the moment. However, you should investigate which disk(s) is getting old and consider replacing it."),
    WarningMessages.W_DISK_FORMAT : lambda : _("Your disk array is experiencing some format issues. To solve this issue, press `Verify` in the Disk Management page."),
}

SUCCESS_MESSAGES = {
    SuccessMessages.S_POOL_CREATED : lambda: _("Disk array created successfully."),
    SuccessMessages.S_POOL_EXPANDED : lambda: _("Disk array expanded successfully."),
    SuccessMessages.S_POOL_FORMATTED : lambda: _("Disk array formatted successfully."), # <----------
    SuccessMessages.S_POOL_DESTROYED : lambda: _("Disk array destroyed successfully."), # <----------

    SuccessMessages.S_APT_UPDATE : lambda: _("System updates retrieved successfully."),
    SuccessMessages.S_APT_UPGRADE : lambda: _("System updates installed successfully."),

    SuccessMessages.S_OTP_DANGEROUS : lambda: _("OTP Accepted. Please press again the button of the desired dangerous operation to continue."),

    SuccessMessages.S_RECOVERY : lambda: _("Disk array recovery attempted."),

    SuccessMessages.S_ACCESS_ENABLED : lambda service : _("Service %(service)s enabled successfully.") % {'service':service},  # <------
    SuccessMessages.S_ACCESS_UPDATED : lambda service : _("Service %(service)s settings updated successfully.") % {'service':service},  # <------
    SuccessMessages.S_ACCESS_DISABLED : lambda service : _("Service %(service)s disabled successfully.") % {'service':service},  # <------

    SuccessMessages.S_DISK_FORMATTED : lambda dev : _("Disk %(dev)s formatted successfully.") % {'dev':dev},  # <------
}