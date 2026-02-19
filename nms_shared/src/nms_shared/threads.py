from abc import abstractmethod, ABCMeta
from typing import Optional, Any
import threading

class NMSThread(metaclass=ABCMeta):
    def __init__(this):
        this._running:bool = False
        this._thread:Optional[threading.Thread] = None
        this._message:Optional[Any] = None
        this._exception:bool = False
        this._eta:Optional[int] = None
        this._progress:Optional[float] = None

    @property
    def is_running(this) -> bool:
        return this._running

    @property
    def has_exception(this) -> bool:
        return this._exception

    @property
    def message(this) -> Optional[Any]:
        return this._message

    @property
    def progress(this) -> Optional[float]:
        return this._progress

    @property
    def eta(this) -> Optional[int]:
        return this._eta

    @property
    def is_successful(this) -> bool:
        return (not (this.is_running or this.has_exception))

    def start(this) -> None:
        if not this.is_running:
            this._thread = threading.Thread(target=this._internal_runner,daemon=True)
            this._thread.start()

    def stop(this) -> None:
        this._running = False

        if (this._thread):
            this._thread.join()

        this._thread = None

    @abstractmethod
    def run(this) -> None:
        pass

    def _internal_runner(this):
        this._running = True
        try:
            this.run()
        except Exception as e:
            this._message = e
            this._exception = True

        this._running = False


