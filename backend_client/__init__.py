from .base import NMSBackend
from .utils import LogFilter, NMSTask

__version__ = "0.1dev"




    # def on_created(this, event):
    #     this.change_ownership(event.src_path)
    #
    # def on_modified(this, event):
    #     this.change_ownership(event.src_path)
    #
    # def _start_tank_observer(this):
    #     path = this.mountpoint
    #
    #     if ((this._watchdog is None) and (path is not None)):
    #         this._watchdog = Observer()
    #         this._watchdog.schedule(this,path,recursive=True)
    #         this._watchdog.start()
    #         this._logger.info("Tank Directory Observer started")



