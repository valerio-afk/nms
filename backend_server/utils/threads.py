from nms_shared.threads import NMSThread
from typing import Optional
import psutil
import time

class NetIOCounter (NMSThread):

    def __init__(this):
        super().__init__()
        this._current_counter = None
        this._bytes_received:int = None
        this._bytes_sent:int = None


    @property
    def bytes_received(this) -> Optional[int]:
        return this._bytes_received if this.is_running else None

    @property
    def bytes_sent(this) -> Optional[int]:
        return this._bytes_sent if this.is_running else None


    def run(this) -> None:
        while (this.is_running):
            counters = psutil.net_io_counters()

            if (this._current_counter is not None):
                this._bytes_received = counters.bytes_recv - this._current_counter.bytes_recv
                this._bytes_sent = counters.bytes_sent - this._current_counter.bytes_sent

            this._current_counter = counters

            time.sleep(1)