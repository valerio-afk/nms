import logging

class Logger:
    def __init__(this):

        this._logger = logging.getLogger("nms.backend")

    def info(this, msg:str) -> None:
        this._logger.info(msg)

    def warning(this, msg:str) -> None:
        this._logger.warning(msg)

    def error(this, msg:str) -> None:
        this._logger.error(msg)