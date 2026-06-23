from dataclasses import dataclass
from enum import Enum
import subprocess
import socket


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


def get_local_ips() -> set[str]:
    ips = {
        "127.0.0.1",
        "::1",
    }

    hostname = socket.gethostname()

    try:
        for info in socket.getaddrinfo(
            hostname,
            None,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_DGRAM,
        ):
            addr = info[4][0]
            ips.add(addr)
    except socket.gaierror:
        pass

    try:
        result = subprocess.run(
            ["ip", "-o", "addr", "show"],
            capture_output=True,
            text=True,
            check=True,
        )

        for line in result.stdout.splitlines():
            # example:
            # 2: eth0    inet 192.168.1.180/24 ...
            parts = line.split()

            if "inet" in parts:
                idx = parts.index("inet")
                ip = parts[idx + 1].split("/")[0]
                ips.add(ip)

            if "inet6" in parts:
                idx = parts.index("inet6")
                ip = parts[idx + 1].split("/")[0]
                ips.add(ip)

    except Exception:
        pass

    return ips