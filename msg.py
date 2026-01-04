from enum import Enum
from typing import Callable,List, Any
from flask_babel import _

def parse_msg(msg:Callable[[List[Any]],str],*args,**kwargs) -> str:
    return str(msg(*args,**kwargs))

class ErrorMessage(Enum):
    E_UNKNOWN = lambda : _("Unknown Error")

    E_POOL_ALREADY_CONF = lambda : _("The disk array is already configured.")
    E_POOL_NO_CONF = lambda: _("Disk array not configured yet.")
    E_POOL_REDUNDANCY_MIN = lambda : _("You must have at least 3 disks connected to opt in redundancy.")
    E_POOL_EXPAND = lambda dev,info : _("Error while adding %(dev)s: %(info)s") % {'dev':dev, 'info':info}#
    E_POOL_EXPAND_INFO = lambda dev : _("Could not retrieve information for the disk: %(dev)s") % {'dev':dev}
    E_POOL_EXPAND_STATUS = lambda info : _("Unable to get array expansion status: %(info)s") % {'info':info}
    E_POOL_ATTACH = lambda details :  _("Unable to attach new device to disk array%(details)s") % {'details':details}
    E_POOL_RECOVERY = lambda info : _("Error while recovering the disk array: %(info)s)") % {'info':info} #
    E_AUTH_INVALID = lambda : _("Invalid authorisation.")
    E_AUTH_EXPIRED = lambda : _("Authorisation token expired.")


    @staticmethod
    def get_error(err_code:"ErrorMessage",*args,**kwargs) -> str:
        return parse_msg(err_code,*args,**kwargs)

class SuccessMessage(Enum):
    S_POOL_CREATED = lambda : _("Disk array created successfully.")
    S_POOL_EXPANDED = lambda : _("Disk array expanded successfully.")

    S_APT_UPDATE = lambda : _("System updates retrieved successfully.")
    S_APT_UPGRADE = lambda : _("System updates installed successfully.")

    S_OTP_DANGEROUS = lambda : _("OTP Accepted. Please press again the button of the desired dangerous operation to continue.")

    S_RECOVERY = lambda : _("Disk array recovery attempted.") #

    @staticmethod
    def get_message(success_code:"SuccessMessage",*args,**kwargs) -> str:
        return parse_msg(success_code,*args,**kwargs)