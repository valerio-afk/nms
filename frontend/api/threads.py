import threading
from typing import Callable
from nms_shared.threads import NMSThread

class TimerThread(NMSThread):

    def __init__(this, interval:int,callback:Callable) -> None:
        super().__init__()
        this._interval:int = interval
        this._callback:Callable = callback
        this._stop_event:threading.Event = threading.Event()

    def run(this) -> None:
        while (this.is_running):
            if this._stop_event.wait(timeout=this._interval):
                break
            this._callback()

    def stop(this) -> None:
        this._stop_event.set()
        super().stop()