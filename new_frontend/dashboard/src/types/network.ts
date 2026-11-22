import type { NetworkInterfaceItem } from './dashboard';

export interface VpnSettings {
    address: string;
    netmask: string;
    endpoint: string;
}

export interface VpnPeerItem {
    name: string;
    ip: string;
}

export interface DdnsProviderConfig {
    enabled: boolean;
    protocol: string;
    server?: string | null;
    username?: string | null;
    password?: string | null;
    hostname?: string | null;
}

export interface DdnsProviderItem {
    name: string;
    enabled: boolean;
    protocol: string;
    server?: string;
    username?: string;
    password?: string;
    hostname?: string;
}

export interface WifiNetworkItem {
    connected: boolean;
    bssid: string;
    ssid: string | null;
    strength: number; // 0 to 4
    security: string | null;
}

export interface WifiConnectPayload {
    ssid: string;
    psk?: string | null;
    profile?: string | null;
}

export interface HotspotPayload {
    iface: string;
    ssid: string;
    psk?: string | null;
}

export interface NetworkPageData {
    interfaces: NetworkInterfaceItem[];
    vpnIface: NetworkInterfaceItem | null;
    vpnEndpoint: string | null;
    vpnPublicKey: string | null;
    vpnPeers: VpnPeerItem[];
    ddnsProviders: DdnsProviderItem[];
    ddnsProtocols: string[];
}
