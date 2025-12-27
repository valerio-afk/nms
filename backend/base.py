from .access_services import AccessServicesMixin
from .auth import AuthMixin
from .config import ConfigMixin
from .daemons import DaemonsMixin
from .dataset import DatasetMixin
from .disks import DiskMixin
from .fs import FSMixin
from .logger import LoggerMixin
from .pool import PoolMixin
from .system import SystemMixin
from .tasks import TaskMixin
from iface import NetworkInterface
import hashlib
import psutil
import socket
import subprocess

hash_password = lambda pwd : hashlib.sha1(pwd.encode()).hexdigest()

class NMSBackend(
    AccessServicesMixin,
    AuthMixin,
    ConfigMixin,
    DaemonsMixin,
    DatasetMixin,
    DiskMixin,
    FSMixin,
    LoggerMixin,
    PoolMixin,
    SystemMixin,
    TaskMixin,
):
    def __new__(cls,*args,**kwargs):
        if not hasattr(cls, 'instance'):
            cls.instance = super(NMSBackend, cls).__new__(cls,*args,**kwargs)
        return cls.instance

    def __init__(this,*args,**kwargs):
        config_file = "nms.json"

        if (kwargs.get("config_file",None) is None):
            kwargs['config_file'] = config_file
        # else:
        #     config_file = kwargs.get("config_file")

        this._watchdog = None

        super().__init__(*args, **kwargs)

        for daemon in this._daemons.values():
            if (daemon is not None):
                daemon.start()

        if (this.is_pool_configured() and (not this.is_mounted)):
            try:
                this.mount()
            except:
                ...




    def iface_status(this):

        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        ifaces = []

        for interface, addr_list in addrs.items():
            is_up = stats[interface].isup if interface in stats else False
            ipv4 = None
            ipv6 = None

            for addr in addr_list:
                if addr.family == socket.AF_INET:
                    ipv4 = addr.address
                elif addr.family == socket.AF_INET6:
                    ipv6 = addr.address

            network_name = None

            try:
                nmcli = ["nmcli", "-t", "-f", "GENERAL.CONNECTION", "device", "show", interface]
                nmcli_output = subprocess.check_output(nmcli, encoding='utf-8').strip().split(":")

                if (len(nmcli_output)==2):
                    network_name = nmcli_output[1].strip()

            except subprocess.CalledProcessError:
                pass

            iface = NetworkInterface(name=interface, status=is_up, ipv4=ipv4, ipv6=ipv6,network_name=network_name)

            ifaces.append(iface)

        ifaces.sort(key=lambda x:x.name)

        return ifaces




































