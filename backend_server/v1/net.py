from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from backend_server.utils.config import CONFIG
from backend_server.utils.daemons import NetIOCounter
from backend_server.v1.auth import verify_token_factory
from typing import Optional, List

import psutil
import subprocess
import socket

net = APIRouter(
    prefix='/net',
    tags=['net'],
    dependencies=[Depends(verify_token_factory())]
)

class NetCounter(BaseModel):
    bytes_sent: Optional[int]
    bytes_recv: Optional[int]

class NetworkInterface(BaseModel):
    name:str
    status:bool
    ipv4: Optional[str]
    ipv6: Optional[str]
    network_name:Optional[str]


@net.get('/io',response_model=NetCounter,responses={500:{'description':'Error while retrieving network information'}})
def net_io_counter() -> NetCounter:
    counter:Optional[NetIOCounter] = CONFIG.net_counter

    if counter is None:
        raise HTTPException(status_code=500,detail='NetIOCounter not available')

    return NetCounter(
        bytes_sent=counter.bytes_sent,
        bytes_recv=counter.bytes_received
    )

@net.get('/ifaces', response_model=List[NetworkInterface])
def net_ifaces() -> List[NetworkInterface]:
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