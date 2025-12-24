from .utils import  LogFilter
from cmdl import RemoteCommandLineTransaction, JournalCtl
from constants import SOCK_PATH
from nms_utils import setup_logger
import socket
from nms_utils import ansi_to_html

class LoggerMixin:

    def __init__(this,*args,**kwargs):
        this._logger = setup_logger("NMS BACKEND")

    @property
    def logger(this):
        return this._logger

    def get_logs(this, what=LogFilter.FLASK):
        grep = None
        service = "nmswebapp.service"
        match (what):
            case LogFilter.CELERY:
                service = "celeryworker.service"
            case LogFilter.SUDODAEMON:
                service = "sudodaemon.service"
            case LogFilter.BACKEND:
                grep = 'NMS BACKEND'

        journalctl = JournalCtl(service,grep)

        trans = RemoteCommandLineTransaction(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,
            journalctl
        )
        output = trans.run()

        if (len(output)==1):
            return ansi_to_html(output[0]['stdout'])
        else:
            return None