import threading, time
import psutil


class NetIOCounter:

    def __init__(this):
        this._running = False
        this._thread = None
        this._current_counter = None
        this._bytes_received = None
        this._bytes_sent = None

    @property
    def is_running(this):
        return this._running

    @property
    def bytes_received(this):
        return this._bytes_received if this.is_running else None

    @property
    def bytes_sent(this):
        return this._bytes_sent if this.is_running else None

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

    def run(this):
        while (this.is_running):
            counters = psutil.net_io_counters()

            if (this._current_counter is not None):
                this._bytes_received = counters.bytes_recv - this._current_counter.bytes_recv
                this._bytes_sent = counters.bytes_sent - this._current_counter.bytes_sent

            this._current_counter = counters

            time.sleep(1)