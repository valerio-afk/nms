from enum import Enum

class DistroFamilies(Enum):
    DEB="apt"
    RH="dnf"
    UNK="unk"

class StatusAction(Enum):
    UP = "up"
    DOWN = "down"

class InterfaceType(Enum):
    ETHERNET = 'ethernet'
    WIFI = 'wifi'
    VPN = 'vpn'
    UNKNOWN = 'unknown'

class SensorType(Enum):
    CPU = 'cpu'
    HDD = 'hdd'
    FAN = 'fan'

class SensorMetric(Enum):
    CELSIUS = '°C'
    RPM = 'RPM'