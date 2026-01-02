from enum import Enum
from typing import Self, Callable, Union, Dict
from flask_babel import lazy_gettext as _, LazyString


class Errors(Enum):
    E_UNK = "E_UNK"
    EPOOL_ALREADY_CONF = "EPOOL_ALREADY_CONF"
    EPOOL_REDUNDANCY_MIN = "EPOOL_REDUNDANCY_MIN"
    EPOOL_EXPAND = "EPOOL_EXPAND"

    @staticmethod
    def get_error(err:Self,**kwargs) -> str:
        err = ERROR_MSGS.get(err,ERROR_MSGS[Errors.E_UNK])
        msg = err

        if (callable(err)):
            msg = err(**kwargs)

        return str(msg)

    @staticmethod
    def raise_error(err:Self):
        raise Exception(err.value)


ERROR_MSGS:Dict[Errors,Union[LazyString,Callable]] = {
    Errors.E_UNK: _("Unknown Error"),
    Errors.EPOOL_ALREADY_CONF : _("The disk array is already configured."),
    Errors.EPOOL_REDUNDANCY_MIN : _("You must have at least 3 disks connected to opt in redundancy."),
    Errors.EPOOL_EXPAND : lambda **params:_("Could not retrieve information for the disk: %(disks)",**params),
}