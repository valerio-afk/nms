from abc import abstractmethod, ABCMeta
from typing import Optional
import psutil
import threading
import time

class NMSThread(metaclass=ABCMeta):
    def __init__(this):
        this._running:bool = False
        this._thread:threading.Thread = None

    @property
    def is_running(this) -> bool:
        return this._running

    def start(this) -> None:
        if not this.is_running:
            this._running = True
            this._thread = threading.Thread(target=this.run,daemon=True)
            this._thread.start()

    def stop(this) -> None:
        this._running = False

        if (this._thread):
            this._thread.join()

        this._thread = None

    @abstractmethod
    def run(this) -> None:
        pass

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