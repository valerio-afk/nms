from logging import getLogger

from nms_shared.utils import setup_logger

setup_logger(__name__)


class Logger:
    def __init__(this):
        this._logger = getLogger(__name__)

    def info(this, msg:str) -> None:
        this._logger.info(msg)

    def warning(this, msg:str) -> None:
        this._logger.warning(msg)

    def error(this, msg:str) -> None:
        this._logger.error(msg)