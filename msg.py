from enum import Enum
from typing import Self, Callable, Union, Dict, Optional
from flask_babel import _

class NMSException(Exception):
    pass

class UnknownError(NMSException):
    def __init__(this):
        super().__init__("E_UNKNOWN")

    def __str__(this) -> str:
        return _("Unknown Error")

    def __repr__(this) -> str:
        return str(this.args)

class PoolAlreadyConfiguredError(NMSException):
    def __init__(this):
        super().__init__("E_POOL_ALREADY_CONF")

    def __str__(this) -> str:
        return _("The disk array is already configured.")

class PoolRedundancyMinRequirementError(NMSException):
    def __init__(this):
        super().__init__("E_POOL_REDUNDANCY_MIN")

    def __str__(this) -> str:
        return _("You must have at least 3 disks connected to opt in redundancy.")

class PoolExpandInfoError(NMSException):
    def __init__(this, device:Optional[str]):
        super().__init__("E_POOL_EXPAND")
        this.device = device


    def __str__(this) -> str:
        return _("Could not retrieve information for the disk: %(dev)s",this.device)


class PoolAttachError(NMSException):
    def __init__(this,details:Optional[str]):
        super().__init__("E_POOL_ATTACH")
        this.details = details

    def __str__(this) -> str:
        details = ""

        if this.details:
            details = f": {this.details}"

        return _("Unable to attach new device to disk array%(details)s",details)
