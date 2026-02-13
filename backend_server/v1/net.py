from enum import Enum
from fastapi.params import Body, Query
from nms_shared.msg import ErrorMessages, SuccessMessages
from nms_shared.constants import WIREGUARD_CONF, VPN_PUBLIC_KEY, VPN_PRIVATE_KEY
from fastapi import APIRouter, HTTPException, Depends
from backend_server.utils.cmdl import NMCLIConnection, NMCLIDevice, LocalCommandLineTransaction, SystemCtlIsActive, \
    SystemCtlStart, SystemCtlStop, SystemCtlRestart
from backend_server.utils.responses import NetCounter, NetworkInterface, IPv4, IPv6, ErrorMessage, InterfaceType, \
    WifiNetwork, WifiConnect, SuccessMessage, VPNServerConf, VPNPeer, DDNSProvider, DDNSDefaultProviderConfiguration
from backend_server.utils.config import CONFIG
from backend_server.utils.threads import NetIOCounter
from backend_server.v1.auth import verify_token_factory
from typing import Optional, List, Tuple, Dict
from collections import OrderedDict
import configparser
import ipaddress
import subprocess
import re
import base64
import io


net = APIRouter(
    prefix='/net',
    tags=['net'],
    dependencies=[Depends(verify_token_factory())]
)

def read_wireguard_config_file() -> configparser.ConfigParser:
    output = subprocess.run(["sudo", "cat", WIREGUARD_CONF], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if (output.returncode != 0):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_NET_CONNECTION_STATUS.name,
                                                                 params=["VPN", output.stderr]))

    config = output.stdout

    counts = {}

    def repl(match):
        name = match.group(1)
        counts[name] = counts.get(name, 0) + 1
        return f"[{name}@{counts[name]}]" if (name.lower() == "peer") else f"[{name}]"

    config = re.sub(r'\[(.*?)\]', repl, config)

    wg = configparser.ConfigParser()
    wg.read_string(config)

    return wg


def write_wireguard_config_file(wg:configparser.ConfigParser) -> None:
    buffer = io.StringIO()
    wg.write(buffer)
    wg_config = buffer.getvalue()

    wg_config = re.sub(r'\[([^\]@]+)@\d+\]', r'[\1]', wg_config)

    result = subprocess.run(
        ["sudo", "tee", WIREGUARD_CONF],
        input=f"{wg_config}\n",
        text=True,
        capture_output=True
    )

    if (result.returncode != 0):
        raise HTTPException(status_code=500, detail="Error while configuring private key")

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

def vpn_status() -> bool:
    service = CONFIG.vpn_service
    if (service is not None):
        cmd = SystemCtlIsActive(service)

        output = cmd.execute()

        if (output.returncode not in [0, 3]):
            raise HTTPException(status_code=500,
                                detail=ErrorMessage(code=ErrorMessages.E_NET_VPN_STATE.name, params=[output.stderr]))

        return False if "inactive" in output.stdout else True

    raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_NET_VPN_NOTCONF.name))

def get_vpn_public_key() -> Optional[str]:
    fname = VPN_PUBLIC_KEY

    result = subprocess.run(
        ["sudo", "cat", fname],
        stdout=subprocess.PIPE,
        check=True
    )

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_POOL_KEY.name,params=[result.stderr.decode('utf8')]))

    return base64.b64encode(result.stdout).decode("ascii")

def get_peers() -> List[Tuple[str,str]]:
    peer_names = CONFIG.vpn_peer_names
    wg_conf = {k: v for k, v in read_wireguard_config_file().items() if k.lower().startswith("peer")}
    peers_ordered = OrderedDict(sorted(wg_conf.items(), key=lambda x: int(x[0].split("@")[1])))

    return list(zip(peer_names, [x.get("allowedips") for x in peers_ordered.values()]))

def vpn_assign_ip() -> Optional[str]:
    used_ips = [ipaddress.IPv4Interface(ip) for _,ip in get_peers()]
    wg_conf = read_wireguard_config_file()
    used_ips.append(ipaddress.IPv4Interface(wg_conf.get("interface","address")))

    network = used_ips[0].network

    # Build a set of used host IPs (faster lookup)
    used_hosts = {iface.ip for iface in used_ips}

    # Find first free IP
    free_ip = None

    for host in network.hosts():  # excludes network and broadcast automatically
        if host not in used_hosts:
            free_ip = ipaddress.IPv4Interface(f"{host}/{network.prefixlen}")
            break

    return str(free_ip)


def get_network_interfaces() -> List[NetworkInterface]:
    cmd = NMCLIDevice("status")
    iface_process = cmd.execute()

    ifaces = [line.split(":") for line in iface_process.stdout.splitlines()]

    network_interfaces = []

    for iface, type, state, connection in ifaces:

        if (type in ['loopback', 'bridge']) or ("unmanaged" in state):
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

            cmd = NMCLIConnection("show", connection)
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
                    pair = line.split(':', 1)
                    property = pair[0].strip()
                    value = pair[1].strip() if len(pair) == 2 else None

                    match (property):
                        case "ipv4.method":
                            ipv4["dynamic"] = False if value == "manual" else True
                        case "ipv4.addresses":
                            if (len(value) > 0):
                                ip = ipaddress.IPv4Interface(value)
                                ipv4["address"] = str(ip.ip)
                                ipv4["netmask"] = str(ip.netmask)
                        case "ipv4.gateway":
                            ipv4["gateway"] = value if (len(value) > 0) else None
                        case "ipv4.dns":
                            values = value.split(",") if value is not None else []
                            ipv4["dns"] = [x for x in values if len(x) > 0]
                        case "ipv6.method":
                            ipv6["dynamic"] = False if value == "manual" else True
                            ipv6["enabled"] = False if value in ["disabled", "ignore"] else True
                        case "IP6.ADDRESS[1]":
                            if (len(value) > 0):
                                ip = ipaddress.IPv6Interface(value)
                                ipv6["address"] = str(ip.ip)
                                ipv6["netmask"] = str(ip.netmask)
                        case "IP6.GATEWAY":
                            ipv6["gateway"] = value if (len(value) > 0) else None
                        case "ipv6.dns":
                            values = value.split(",") if value is not None else []
                            ipv6["dns"] = [x for x in values if len(x) > 0]
                        case _:
                            if ("=" in value):
                                try:
                                    sub_property, sub_value = value.split("=")
                                    sub_property = sub_property.strip()
                                    sub_value = sub_value.strip()

                                    match (sub_property):
                                        case "ip_address":
                                            ipv4["address"] = sub_value if len(sub_value) > 0 else None
                                        case "subnet_mask":
                                            ipv4["netmask"] = sub_value
                                        case "domain_name_servers":
                                            ipv4["dns"] = [sub_value]
                                        case "routers":
                                            ipv4["gateway"] = sub_value
                                except ValueError:
                                    ...

                ipv4_info = IPv4(**ipv4)
                ipv6_info = IPv6(**ipv6)

            else:
                raise HTTPException(status_code=500,
                                    detail=ErrorMessage(code=ErrorMessages.E_NET_CONNECTION_STATUS.name,
                                                        params=[iface, output.stderr]))

        network_interface = NetworkInterface(ipv4=ipv4_info, ipv6=ipv6_info, **network_params)
        network_interfaces.append(network_interface)

    return network_interfaces

@net.get('/io',response_model=NetCounter,responses={500:{'description':'Error while retrieving network information'}})
def net_io_counter() -> NetCounter:
    return net_io_counter()

@net.get('/ifaces', response_model=List[NetworkInterface])
def net_ifaces() -> List[NetworkInterface]:
    return get_network_interfaces()
#
# @net.get("/vpn/status",response_model=bool)
# def get_vpn_status() -> bool:
#     return vpn_status()


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


@net.get("/vpn/pubkey",response_model=str)
def net_vpn_pubkey() -> str:
    return get_vpn_public_key()

@net.get("/vpn/public-ip",response_model=Optional[str])
def net_vpn_endpoint() -> Optional[str]:
    return CONFIG.vpn_public_ip

@net.get("/vpn/peers",response_model=List[Tuple[str,str]])
def net_vpn_peers() -> List[Tuple[str, str]]:
    return get_peers()



@net.post("/vpn/peers/remove")
def net_vpn_peer_remove(name:str=Query(...)) -> dict:
    peers = CONFIG.vpn_peer_names

    try:
        idx = peers.index(name)
    except ValueError:
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_NET_VPN_USER.name, params=[name]))

    CONFIG.vpn_remove_peer(idx)

    wg_conf = read_wireguard_config_file()
    section_name = None
    pattern = f"peer@{idx+1}"

    for k,v in wg_conf.items():
        if (k.lower() == pattern):
            section_name = k
            break

    if (section_name is not None):
        wg_conf.remove_section(section_name)

    write_wireguard_config_file(wg_conf)
    CONFIG.flush_config()

    SystemCtlRestart(CONFIG.vpn_service).execute()

    return {"detail":SuccessMessage(code=SuccessMessages.S_NET_VPN_PEER_DELETED.name,params=[name])}

@net.post("/vpn/peers/add")
def net_vpn_peer_add(peer:VPNPeer) -> dict:
    name = peer.name.strip()

    if (len(name)==0):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_NET_VPN_USER_INVALID.name))

    try:
        CONFIG.vpn_peer_names.index(name)
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_NET_VPN_USER_INVALID.name))
    except ValueError:
        ... #no duplicates


    idx = CONFIG.vpn_add_peer(name)
    public_ip = CONFIG.vpn_public_ip
    assigned_ip = vpn_assign_ip()

    if (assigned_ip is None):
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_NET_VPN_IP_MAX.name))



    wg_conf = read_wireguard_config_file()
    section_name = f"Peer@{idx}"

    wg_conf.add_section(section_name)
    wg_conf.set(section_name,"PublicKey",peer.public_key)
    wg_conf.set(section_name, "AllowedIPs", assigned_ip)
    wg_conf.set(section_name, "PersistentKeepalive", f"25")
    wg_conf.set(section_name, "Endpoint", f"{public_ip}:51820")

    write_wireguard_config_file(wg_conf)
    CONFIG.flush_config()

    SystemCtlRestart(CONFIG.vpn_service).execute()

    return {"detail":SuccessMessage(code=SuccessMessages.S_NET_VPN_PEER_ADDED.name,params=[name])}


@net.post("/vpn/gen-keys")
def net_vpn_genkey() -> dict:
    result = subprocess.run(
        ["wg", "genkey"],
        capture_output=True,
        text=True
    )

    if (result.returncode != 0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_VPN_GEN_PRIVATE.name,params=[result.stdout]))

    private_key = result.stdout.strip()

    result = subprocess.run(
        ["sudo", "tee", VPN_PRIVATE_KEY],
        input=f"{private_key}\n",
        text=True,
        capture_output=True
    )

    if (result.returncode != 0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_VPN_GEN_PRIVATE.name,params=[result.stdout]))

    wg = read_wireguard_config_file()

    wg['interface']['PrivateKey']= private_key

    write_wireguard_config_file(wg)

    result = subprocess.run(
        ["wg", "pubkey"],
        input=private_key,
        capture_output=True,
        text=True
    )

    if (result.returncode != 0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_VPN_GEN_PUBLIC.name,params=[result.stdout]))

    public_key = result.stdout.strip()

    result = subprocess.run(
        ["sudo", "tee", VPN_PUBLIC_KEY],
        input=f"{public_key}\n",
        text=True,
        capture_output=True
    )

    if (result.returncode != 0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_VPN_GEN_PUBLIC.name,params=[result.stdout]))

    return {"detail": SuccessMessage(code=SuccessMessages.S_NET_VPN_KEYSGEN.name)}


@net.post("/vpn/config")
def net_vpn_config(config:VPNServerConf) -> dict:
    netmask = config.netmask
    try:
        netmask = ipaddress.IPv4Address(netmask)
        prefix = bin(int(netmask)).count("1")
    except ipaddress.AddressValueError:
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_NET_INVALID_NETMASK.name))

    ip_address = config.address

    try:
        ip_address = ipaddress.IPv4Address(ip_address)
    except ipaddress.AddressValueError:
        raise HTTPException(status_code=500, detail=ErrorMessage(code=ErrorMessages.E_NET_INVALID_IP_ADDRESS.name))

    wg = read_wireguard_config_file()
    wg['interface']['Address'] = f"{str(ip_address)}/{prefix}"

    for section in wg.sections():
        if section.lower().startswith("peer"):
            wg.set(section,"endpoint",f"{config.endpoint}:51820")

    write_wireguard_config_file(wg)

    CONFIG.vpn_public_ip = config.endpoint
    CONFIG.flush_config()

    SystemCtlRestart(CONFIG.vpn_service).execute()

    return {"detail": SuccessMessage(code=SuccessMessages.S_NET_VPN_CONFIG.name)}

@net.post('/vpn/{action}')
def net_iface_action(action:IFaceAction) -> None:
    cmd = None
    vpn_service = CONFIG.vpn_service

    match(action):
        case IFaceAction.UP:
            cmd = SystemCtlStart(vpn_service)
        case IFaceAction.DOWN:
            cmd = SystemCtlStop(vpn_service)

    output = cmd.execute()

    if (output.returncode != 0):
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_CHANGE_STATE.name,params=["VPN",output.stderr]))

@net.get('/vpn',response_model=NetworkInterface)
def net_get_vpn_config() -> NetworkInterface:
    wg = read_wireguard_config_file()

    ip = ipaddress.IPv4Interface(wg['interface']['Address'])
    ipv4 = {
        "address": str(ip.ip) ,
        "netmask": str(ip.netmask),
        "dynamic": False,
    }
    network = NetworkInterface(name="vpn",
                               enabled=vpn_status(),
                               has_profile=False,
                               ipv4=IPv4(**ipv4),
                               network_name="VPN",
                               type=InterfaceType.VPN)
    return network


@net.post('/{iface}/{action}')
def net_iface_action(iface:str,action:IFaceAction) -> None:
    match(action):
        case IFaceAction.UP:
            perform="connect"
        case IFaceAction.DOWN:
            perform = "disconnect"

    cmds = [NMCLIDevice(perform,iface,sudo=True)]


    if (action == IFaceAction.DOWN):
        ifaces = get_network_interfaces()
        for x in ifaces:
            if ((x.name != iface) and (x.enabled)):
                cmds += [
                    NMCLIConnection("down",x.network_name,sudo=True),
                    NMCLIConnection("up", x.network_name, sudo=True),
                ]

    trans = LocalCommandLineTransaction(*cmds)
    output = trans.run()


    if (not trans.success):
        error = "\n".join([x['stderr'] for x in output])
        raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_CHANGE_STATE.name,params=[iface,error]))




@net.post('/{iface}/{ip_version}/config')
def net_iface_settings(iface:str,
                       ip_version:str,
                       settings:dict=Body(...),
                       profile:str=Query(...)) -> dict:

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

    return {"detail": SuccessMessage(code=SuccessMessages.S_NET_CONFIG.name,params=[iface])}

@net.get('/ddns/providers',response_model=Dict[str,DDNSProvider])
def ddns_provider_list() -> Dict[str,DDNSProvider]:
    providers = {name:DDNSProvider(
        enabled=props["enabled"],
        username=props["username"],
        last_update=props["last_update"])
        for name,props in CONFIG.ddns_providers.items()}

    for k,v in providers.items():
        if (v.enabled):
            force_disable = False
            try:
                thread = CONFIG.check_daemon(k,"ddns")
                v.last_update = thread.last_update
                v.next_update = thread.next_update
                CONFIG.ddns_provider_set_last_update(k,v.last_update)
            except HTTPException as e:
                force_disable = True
                raise e
            except Exception as e:
                force_disable = True
                raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_DDNS_SERVICE.name,params=[k,str(e)]))
            finally:
                if (force_disable):
                    CONFIG.ddns_provider_enabled(k,False)
                    CONFIG.flush_config()


    return providers

@net.post('/ddns/{provider}/start')
def ddns_provider_start(provider:str,config:Optional[DDNSDefaultProviderConfiguration]=None) -> dict:
    match (provider):
        case "noip":
            if (config is not None):
                CONFIG.ddns_noip_set(config.username,config.password)
            CONFIG.ddns_noip_start()
        case "duckdns":
            if (config is not None):
                CONFIG.ddns_duckdns_set(config.username, config.password)
            CONFIG.ddns_duckdns_start()
        case "dynu":
            if (config is not None):
                CONFIG.ddns_dynu_set(config.username, config.password)
            CONFIG.ddns_dynu_start()
        case _:
            raise HTTPException(status_code=500,detail=ErrorMessage(code=ErrorMessages.E_NET_DDNS_INVALID.name,params=[provider]))

    CONFIG.flush_config()


    return {"details":SuccessMessage(code=SuccessMessages.S_NET_DDNS_ENABLED.name,params=[provider])}

@net.post('/ddns/{provider}/stop')
def ddns_provider_stop(provider:str) -> dict:
    CONFIG.ddns_stop(provider.lower())
    CONFIG.flush_config()
    return {"details":SuccessMessage(code=SuccessMessages.S_NET_DDNS_DISABLED.name,params=[provider])}
