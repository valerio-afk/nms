from abc import abstractmethod, ABCMeta
from typing import Optional
import threading

class NMSThread(metaclass=ABCMeta):
    def __init__(this):
        this._running:bool = False
        this._thread:Optional[threading.Thread] = None
        this._exception:Optional[Exception] = None

    @property
    def is_running(this) -> bool:
        return this._running

    @property
    def exception(this) -> Optional[Exception]:
        return this._exception

    @property
    def is_successful(this) -> bool:
        return (not this.is_running) and (this.exception is None)

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

    def internal_runner(this):
        try:
            this.run()
        except Exception as e:
            this._exception = e


