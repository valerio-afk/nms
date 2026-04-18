from dataclasses import dataclass
from enum import Enum



class TransportProtocol(Enum):
    TCP = 'tcp'
    UDP = 'udp'


class GenericTransportPort():
    ...

@dataclass(frozen=True)
class SinglePort(GenericTransportPort):
    port:int

    def __str__(this):
        return str(this.port)

@dataclass(frozen=True)
class PortRange(GenericTransportPort):
    port_min:int
    port_max:int

    def __str__(this):
        return f"{this.port_min}-{this.port_max}"

def str2port(port_str:str) -> GenericTransportPort:
    try:
        port = int(port_str)
        return SinglePort(port)
    except ValueError:
        try:
            port_min,port_max = [int(p) for p in port_str.split("-")]
            return PortRange(port_min,port_max)
        except ValueError:
            raise Exception(f"Invalid port or port range {port_str}")