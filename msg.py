from enum import Enum
from typing import Self, Callable, Union, Dict, Optional
from flask_babel import _

class ErrorMessage(Enum):
    E_UNKNOWN = _("Unknown Error")
    E_POOL_ALREADY_CONF = _("The disk array is already configured.")
    E_POOL_REDUNDANCY_MIN = _("You must have at least 3 disks connected to opt in redundancy.")
    E_POOL_EXPAND = lambda dev : _("Could not retrieve information for the disk: %(dev)s",dev)
    E_POOL_ATTACH = lambda details :  _("Unable to attach new device to disk array%(details)s",details)

    @staticmethod
    def get_error(err_code:Self,*args,**kwargs):
        msg = err_code.value

        if (callable(msg)):
            msg = msg(*args,**kwargs)

        return str(msg)
