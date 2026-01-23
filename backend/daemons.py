
from typing import Dict


from backend_server.utils.cmdl import ZPoolScrub, RemoteCommandLineTransaction, ZPoolStatus
from constants import SOCK_PATH
from flask import flash
from flask_daemons import NetIOCounter, ScrubStateChecker, CheckConfigFile
import datetime
import json
import socket


def scrub_finished_hook():
    flash("Disk array verification completed","success")


class DaemonsMixin():

    def __init__(this,*args,**kwargs):
        super().__init__(*args,**kwargs)
        this._daemons = {
            'net_counters':NetIOCounter(),
            'scrub_checker':None,
            'inotify': CheckConfigFile(this.config_filename,this.load_configuration_file),
        }


    @property
    def get_net_counters(this)  -> Dict[str,int]:
        net_io = this._daemons['net_counters']
        return {"received": net_io.bytes_received, "sent": net_io.bytes_sent}

    @property
    def get_scrub_info(this) -> Dict[str,str]:
        return {k: v for k, v in this.cfg['pool'].get('tools', {}).get('scrub', {}).items()}


    def check_scrub_status(this) -> None:
        if (this.cfg['pool']['tools']['scrub']['ongoing'] == True):
            daemon:ScrubStateChecker = this._daemons['scrub_checker']

            if (daemon is not None):
                if (not daemon.is_running):
                    this.cfg['pool']['tools']['scrub']['ongoing'] = False
                    this.flush_config()
                    this._daemons['scrub_checker'] = None
                    this._logger.info(f"Scrub checker thread terminated {daemon.completion_handler}")
                    scrub_finished_hook()
            else:
                daemon = ScrubStateChecker(this.pool_name)
                this._daemons['scrub_checker'] = daemon
                daemon.start()
                this._logger.info("Scrub checker thread started")

    def get_last_scrub_report(this) -> Dict[str,str]:
        output = ZPoolStatus(this.pool_name).execute()


        if (output.returncode == 0):
            d = json.loads(output.stdout)
            scan_stats = d.get('pools', {}).get(this.pool_name, {}).get('scan_stats', {})

            if (scan_stats.get('function', "") == "SCRUB"):
                started = int(scan_stats.get('start_time', -1))
                ended = int(scan_stats.get('end_time', -1))
                errors = scan_stats.get('errors', "-")

                started = datetime.datetime.fromtimestamp(started).strftime("%c") if started >=0 else "-"
                ended = datetime.datetime.fromtimestamp(ended).strftime("%c") if ended >= 0 else "-"

                return {
                    'Started at': started,
                    'Ended at': ended,
                    "Errors": errors
                }

        return None

    def start_scrub(this) -> None:
        pool = this.pool_name

        if (pool is None):
            raise Exception("No disk array found")

        command = ZPoolScrub(pool)
        trans = RemoteCommandLineTransaction(socket.AF_UNIX,
            socket.SOCK_STREAM,
            SOCK_PATH,command)

        output = trans.run()

        if (len(output)!=1):
            raise Exception("Unknown Error")

        if (output[0]['returncode']!=0):
            raise Exception (output[0]['stderr'])

        this.cfg['pool']['tools']['scrub']['ongoing'] = True
        this.cfg['pool']['tools']['scrub']['last'] = datetime.datetime.now().timestamp()

        this.flush_config()