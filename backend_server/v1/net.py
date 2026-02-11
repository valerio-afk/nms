from enum import Enum
from fastapi.params import Body, Query
from nms_shared.msg import ErrorMessages
from fastapi import APIRouter, HTTPException, Depends
from backend_server.utils.cmdl import NMCLIConnection, NMCLIDevice, LocalCommandLineTransaction
from backend_server.utils.responses import NetCounter, NetworkInterface, IPv4, IPv6, ErrorMessage, InterfaceType, \
    WifiNetwork, WifiConnect
from backend_server.utils.config import CONFIG
from backend_server.utils.threads import NetIOCounter
from backend_server.v1.auth import verify_token_factory
from typing import Optional, List
import ipaddress
import re

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


class IFaceAction(Enum):
    UP = "up"
    DOWN = "down"




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


        iface_type = InterfaceType.UNKNOWN

        match (type.strip()):
            case "ethernet":
                iface_type = InterfaceType.ETHERNET
            case "wifi":
                iface_type = InterfaceType.WIFI
            case _:
                continue

        iface_enabled = True if state.startswith("connected") else False

        network_params = {
            'name': iface,
            'enabled': iface_enabled,
            'network_name': connection,
            'type': iface_type,
            'has_profile': False
        }

        ipv4_info = None
        ipv6_info = None

        if (iface_enabled):

            cmd = NMCLIConnection("show",connection)
            output = cmd.execute()

            if (output.returncode == 0):
                network_params['has_profile'] = True
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
                            if (len(value)>0):
                                ip = ipaddress.IPv4Interface(value)
                                ipv4["address"] = str(ip.ip)
                                ipv4["netmask"] = str(ip.netmask)
                        case "ipv4.gateway":
                            ipv4["gateway"] = value if (len(value)>0) else None
                        case "ipv4.dns":
                            values = value.split(",") if value is not None else []
                            ipv4["dns"] = [x for x in values if len(x)>0]
                        case "ipv6.method":
                            ipv6["dynamic"] = False if value == "manual" else True
                            ipv6["enabled"] = False if value in ["disabled","ignore"] else True
                        case "IP6.ADDRESS[1]":
                            if (len(value) > 0):
                                ip = ipaddress.IPv6Interface(value)
                                ipv6["address"] = str(ip.ip)
                                ipv6["netmask"] = str(ip.netmask)
                        case "IP6.GATEWAY":
                            ipv6["gateway"] = value if (len(value)>0) else None
                        case "ipv6.dns":
                            values = value.split(",") if value is not None else []
                            ipv6["dns"] = [x for x in values if len(x)>0]
                        case _:
                            if ("=" in value):
                                try:
                                    sub_property,sub_value = value.split("=")
                                    sub_property = sub_property.strip()
                                    sub_value = sub_value.strip()

                                    match (sub_property):
                                        case "ip_address": ipv4["address"] = sub_value if len(sub_value)>0 else None
                                        case "subnet_mask": ipv4["netmask"] = sub_value
                                        case "domain_name_servers": ipv4["dns"] = [sub_value]
                                        case "routers": ipv4["gateway"] = sub_value
                                except ValueError:
                                    ...



                ipv4_info = IPv4(**ipv4)
                ipv6_info = IPv6(**ipv6)

            else:
                raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_CONNECTION_STATUS.name,params=[iface,output.stderr]))

        network_interface = NetworkInterface(ipv4=ipv4_info,ipv6=ipv6_info,**network_params)
        network_interfaces.append(network_interface)

    return network_interfaces


@net.get('/{iface}/list',response_model=List[WifiNetwork])
def net_wifi_networks(iface:str) -> List[WifiNetwork]:
    cmd = NMCLIDevice("wifi","list","ifname",iface,sudo=True)
    output = cmd.execute()

    if (output.returncode != 0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_WIFI_LIST.name,params=[iface,output.stderr]))

    networks = []

    for network in output.stdout.splitlines():
        in_use,bssid,ssid,_,_,_,_,bars,security = re.split(r'(?<!\\):', network)

        networks.append(WifiNetwork(connected=True if len(in_use.strip())>0 else False,
                                    bssid=bssid.replace('\\:',':').strip(),
                                    ssid=ssid.strip() if ssid.strip() != "--" else None,
                                    strength=4-bars.strip().count("_"),
                                    security=security.strip() if security.strip() != "--" else None,
                        ))

    return networks

@net.post('/{iface}/connect')
def net_wifi_connect(iface:str,network:WifiConnect) -> None:
    if (network.ssid is None):
        return

    profile_name = network.profile if network.profile else network.ssid

    NMCLIConnection("delete",profile_name,sudo=True).execute()

    add_profile = NMCLIConnection("add",
                          "type","wifi",
                          "con-name",network.ssid,
                          "ifname",iface,
                          "ssid",network.ssid,
                          sudo=True)

    if (network.psk is not None):
        add_profile.append(["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk",network.psk])

    connection_up = NMCLIConnection("up",profile_name,sudo=True)

    trans = LocalCommandLineTransaction(add_profile,connection_up)
    output = trans.run()


    if (not trans.success):
        error = "\n".join([x['stderr'] for x in output])
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_WIFI_CONNECT.name,params=[network.ssid, error]))


@net.post('/{iface}/{action}')
def net_iface_action(iface:str,action:IFaceAction) -> None:
    match(action):
        case IFaceAction.UP:
            perform="connect"
        case IFaceAction.DOWN:
            perform = "disconnect"

    cmd = NMCLIDevice(perform,iface,sudo=True)
    output = cmd.execute()

    if (output.returncode != 0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_CHANGE_STATE.name,params=[iface,output.stderr]))




@net.post('/{iface}/{ip_version}/config')
def net_iface_settings(iface:str,
                       ip_version:str,
                       settings:dict=Body(...),
                       profile:str=Query(...)) -> None:

    cmds = []

    ip_version = ip_version.lower()

    if (("enabled" in settings) and (settings['enabled'] == False)):
        modify_method = NMCLIConnection("modify", profile, f"{ip_version}.method", "disabled")
        cmds.append(modify_method)
    else:
        dhcp = settings.get("dynamic")

        modify_cmd = NMCLIConnection("modify", profile, f"{ip_version}.method", "auto" if dhcp else "manual")

        if (not dhcp):
            netmask = settings.get("netmask")
            try:
                netmask = ipaddress.IPv4Address(netmask) if ip_version == "ipv4" else ipaddress.IPv6Address(netmask)
                prefix = bin(int(netmask)).count("1")
            except ipaddress.AddressValueError:
                raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_NET_INVALID_NETMASK.name))

            ip_address = settings.get("address")
            try:
                ip_address = ipaddress.IPv4Address(ip_address) if ip_version == "ipv4" else ipaddress.IPv6Address(ip_address)
            except ipaddress.AddressValueError:
                raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_NET_INVALID_IP_ADDRESS.name))

            modify_cmd.append([f"{ip_version}.addresses", f"{ip_address}/{prefix}"])


            gateway = settings.get("gateway")
            if ((gateway is not None) and (len(gateway)>0)):
                gateway = settings.get("gateway")
                try:
                    gateway = ipaddress.IPv4Address(gateway) if ip_version == "ipv4" else ipaddress.IPv6Address(
                        gateway)
                except ipaddress.AddressValueError:
                    raise HTTPException(status_code=500,
                                        detail=ErrorMessage(code=ErrorMessages.E_NET_INVALID_GATEWAY.name))

                modify_cmd.append([f"{ip_version}.gateway", f"{gateway}"])


            dns = settings.get("dns")
            if ((dns is not None) and (len(dns)>0)):
                try:
                    dns_addresses = [str(ipaddress.IPv4Address(x) if ip_version == "ipv4" else ipaddress.IPv6Address(x)) for x in dns]
                    modify_cmd.append([f"{ip_version}.dns", ','.join(dns_addresses)])
                except ipaddress.AddressValueError:
                    raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_INVALID_DNS.name))

        cmds.append(modify_cmd)


    reapply = NMCLIDevice("reapply",iface)
    cmds.append(reapply)

    trans = LocalCommandLineTransaction(*cmds,privileged=True)
    output = trans.run()

    if (not trans.success):
        error = "\n".join([t['stderr'] for t in output])
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_CHANGE_STATE.name,params=[iface,error]))