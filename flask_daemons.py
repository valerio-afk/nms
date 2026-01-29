from typing import Callable
from backend_server.utils.cmdl import ZPoolStatus
import os
import threading, time
import json
from nms_shared.threads import NMSThread







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