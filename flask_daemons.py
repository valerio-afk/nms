from typing import Callable
from abc import abstractmethod
from backend_server.utils.cmdl import ZPoolStatus
import os
import threading, time
import psutil
import json



class NMSThread:
    def __init__(this):
        this._running = False
        this._thread = None

    @property
    def is_running(this):
        return this._running

    def start(this):
        if not this.is_running:
            this._running = True
            this._thread = threading.Thread(target=this.run,daemon=True)
            this._thread.start()

    def stop(this):
        this._running = False

        if (this._thread):
            this._thread.join()

        this._thread = None

    @abstractmethod
    def run(this):
        pass

class NetIOCounter (NMSThread):

    def __init__(this):
        super().__init__()
        this._current_counter = None
        this._bytes_received = None
        this._bytes_sent = None


    @property
    def bytes_received(this):
        return this._bytes_received if this.is_running else None

    @property
    def bytes_sent(this):
        return this._bytes_sent if this.is_running else None


    def run(this):
        while (this.is_running):
            counters = psutil.net_io_counters()

            if (this._current_counter is not None):
                this._bytes_received = counters.bytes_recv - this._current_counter.bytes_recv
                this._bytes_sent = counters.bytes_sent - this._current_counter.bytes_sent

            this._current_counter = counters

            time.sleep(1)

class ScrubStateChecker(NMSThread):

    def __init__(this,pool):
        super().__init__()
        this.pool = pool
        this.completion_handler = None


    def start(this):
        if not this.is_running:
            this._running = True
            this._thread = threading.Thread(target=this.run,daemon=True)
            this._thread.start()


    def run(this):
        while (this.is_running):
            output = ZPoolStatus(this.pool).execute()

            if (output.returncode == 0):
                d = json.loads(output.stdout)
                scan_stats = d.get('pools', {}).get(this.pool, {}).get('scan_stats', {})

                if (scan_stats.get('function',"") == "SCRUB"):
                    if (scan_stats.get('state',"FINISHED") != "FINISHED"):
                        time.sleep(2)
                    else:
                        break
                else:
                    break
            else:
                break

        this._running = False
        this._thread = None

        if (this.completion_handler is not None):
            this.completion_handler()

class CheckConfigFile(NMSThread):
    def __init__(this,filename:str, callback:Callable,interval:float=1):
        super().__init__()
        this._filename = filename
        this._callback = callback
        this._interval = interval

    def run(this):
        last_mtime = None

        while (this.is_running):
            try:
                mtime = os.stat(this._filename).st_mtime
                if ((last_mtime is not None) and (mtime != last_mtime)):
                    this._callback()

                last_mtime = mtime
            except:
                ...

            time.sleep(this._interval)