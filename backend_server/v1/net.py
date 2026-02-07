from fastapi import APIRouter, HTTPException, Depends

from backend_server.utils.cmdl import NMCLIConnection, NMCLIDevice
from backend_server.utils.responses import NetCounter, NetworkInterface, IPv4, IPv6
from backend_server.utils.config import CONFIG
from backend_server.utils.threads import NetIOCounter
from backend_server.v1.auth import verify_token_factory
from typing import Optional, List
import ipaddress

net = APIRouter(
    prefix='/net',
    tags=['net'],
    dependencies=[Depends(verify_token_factory())]
)

def net_counter() -> NetCounter:
    counter:Optional[NetIOCounter] = CONFIG.net_counter

    if counter is None:
        raise HTTPException(status_code=500,detail='NetIOCounter not available')

    return NetCounter(
        bytes_sent=counter.bytes_sent,
        bytes_recv=counter.bytes_received
    )


@net.get('/io',response_model=NetCounter,responses={500:{'description':'Error while retrieving network information'}})
def net_io_counter() -> NetCounter:
    return net_io_counter()

@net.get('/ifaces', response_model=List[NetworkInterface])
def net_ifaces() -> List[NetworkInterface]:
    cmd = NMCLIDevice("status")
    iface_process = cmd.execute()

    ifaces = [ line.split(":") for line in iface_process.stdout.splitlines() ]

    network_interfaces = []


    for iface,type,state,connection in ifaces:

        if (type in ['loopback','bridge']) or ("unmanaged" in state):
            continue

        cmd = NMCLIConnection("show",iface)
        output = cmd.execute()

        if (output.returncode == 0):
            network_params  = {
                'name' : iface,
                'enabled': True if state.startswith("connected") else False,
                'network_name': connection
            }

            ipv4 = {
                'dynamic': False,
                'address': None,
                'netmask': None,
                'gateway': None,
                'dns': [],
            }

            ipv6 = {
                'enabled': False,
                'dynamic': False,
                'address': None,
                'netmask': None,
                'gateway': None,
                'dns': [],
            }

            for line in output.stdout.splitlines():
                pair = line.split(':',1)
                property = pair[0].strip()
                value = pair[1].strip() if len(pair) == 2 else None

                match (property):
                    case "ipv4.method":
                        ipv4["dynamic"] = False if value =="manual" else True
                    case "ipv4.addresses":
                        ip = ipaddress.IPv4Interface(value)
                        ipv4["address"] = str(ip.ip)
                        ipv4["netmask"] = str(ip.netmask)
                    case "ipv4.gateway":
                        ipv4["gateway"] = value
                    case "ipv4.dns":
                        values = value.split(",") if value is not None else []
                        ipv4["dns"] = [x for x in values if len(x)>0]
                    case "ipv6.method":
                        ipv6["dynamic"] = False if value == "manual" else True
                        ipv6["enabled"] = False if value in ["disabled","ignore"] else True
                    case "IP6.ADDRESS[1]":
                        ip = ipaddress.IPv6Interface(value)
                        ipv6["address"] = str(ip.ip)
                        ipv6["netmask"] = str(ip.netmask)
                    case "IP6.GATEWAY":
                        ipv6["gateway"] = value
                    case "ipv6.dns":
                        values = value.split(",") if value is not None else []
                        ipv6["dns"] = [x for x in values if len(x)>0]

            ipv4_info = IPv4(**ipv4)
            ipv6_info = IPv6(**ipv6)

            network_interface = NetworkInterface(ipv4=ipv4_info,ipv6=ipv6_info,**network_params)
            network_interfaces.append(network_interface)

    return network_interfaces


# def net_ifaces() -> List[NetworkInterface]:
#     addrs = psutil.net_if_addrs()
#     stats = psutil.net_if_stats()
#
#     ifaces = []
#
#     for interface, addr_list in addrs.items():
#         is_up = stats[interface].isup if interface in stats else False
#         ipv4 = None
#         ipv6 = None
#
#         for addr in addr_list:
#             if addr.family == socket.AF_INET:
#                 ipv4 = addr.address
#             elif addr.family == socket.AF_INET6:
#                 ipv6 = addr.address
#
#         network_name = None
#
#         try:
#             nmcli = ["nmcli", "-t", "-f", "GENERAL.CONNECTION", "device", "show", interface]
#             nmcli_output = subprocess.check_output(nmcli, encoding='utf-8').strip().split(":")
#
#             if (len(nmcli_output)==2):
#                 network_name = nmcli_output[1].strip()
#
#         except subprocess.CalledProcessError:
#             pass
#
#         iface = NetworkInterface(name=interface, status=is_up, ipv4=ipv4, ipv6=ipv6,network_name=network_name)
#
#         ifaces.append(iface)
#
#     ifaces.sort(key=lambda x:x.name)
#
#     return ifaces