from typing import Dict
from backend_server.utils.cmdl import ZPoolScrub, RemoteCommandLineTransaction, ZPoolStatus
from flask import flash
from flask_daemons import NetIOCounter, ScrubStateChecker, CheckConfigFile
import datetime
import json
import socket


def scrub_finished_hook():
    flash("Disk array verification completed","success")


class DaemonsMixin():

    @property
    def get_net_counters(this)  -> Dict[str,int]:
        ...

    @property
    def get_scrub_info(this) -> Dict[str,str]:
        ...


    def check_scrub_status(this) -> None:
        ...

    def get_last_scrub_report(this) -> Dict[str,str]:
        ...

    def start_scrub(this) -> None:
        ...
        # pool = this.pool_name
        #
        # if (pool is None):
        #     raise Exception("No disk array found")
        #
        # command = ZPoolScrub(pool)
        # trans = RemoteCommandLineTransaction(socket.AF_UNIX,
        #     socket.SOCK_STREAM,
        #     SOCK_PATH,command)
        #
        # output = trans.run()
        #
        # if (len(output)!=1):
        #     raise Exception("Unknown Error")
        #
        # if (output[0]['returncode']!=0):
        #     raise Exception (output[0]['stderr'])
        #
        # this.cfg['pool']['tools']['scrub']['ongoing'] = True
        # this.cfg['pool']['tools']['scrub']['last'] = datetime.datetime.now().timestamp()
        #
        # this.flush_config()