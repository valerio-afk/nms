export interface PoolCapacity {
    used: number;
    total: number;
}

export interface PoolSettings {
    encryption: boolean;
    redundancy: boolean;
    compression: boolean;
}

export interface PoolStatus {
    isConfigured: boolean;
    isMounted: boolean;
    capacity: PoolCapacity | null;
    settings?: PoolSettings | null;
}

export type DiskStatusCode = 'ONLINE' | 'NEW' | 'OFFLINE' | 'CORRUPTED' | 'UNKNOWN';

export interface DiskItem {
    name: string;
    model: string;
    serial?: string;
    size?: number | null;
    status: DiskStatusCode;
    statusCode: number; // 1 = ONLINE, 0 = NEW, -1 = OFFLINE, -2 = CORRUPTED, -3 = UNKNOWN
    path?: string;
    physical_paths?: string[];
    inPool: boolean;
    temperature?: number;
}

export interface NetworkIPv4 {
    dynamic: boolean;
    address?: string | null;
    netmask?: string | null;
    gateway?: string | null;
    dns?: string[];
}

export interface NetworkIPv6 {
    enabled?: boolean;
    dynamic?: boolean;
    address?: string | null;
    netmask?: string | null;
    gateway?: string | null;
    dns?: string[];
}

export type NetworkIfaceType = 'ethernet' | 'wifi' | 'vpn' | 'other' | 'unknown';

export interface NetworkInterfaceItem {
    name: string;
    enabled: boolean;
    network_name?: string;
    type: NetworkIfaceType;
    ipv4?: NetworkIPv4 | null;
    ipv6?: NetworkIPv6 | null;
    has_profile?: boolean;
    ap?: boolean | null;
    status: 'up' | 'down';
    ipAddress?: string;
    rxBytes?: number;
    txBytes?: number;
}

export interface RemoteServiceItem {
    id: string;
    name: string;
    active: boolean;
}

export interface SystemNetCounters {
    bytes_recv: number;
    bytes_sent: number;
    total_bytes_recv?: number;
    total_bytes_sent?: number;
}

export interface SystemInfo {
    hostname?: string;
    os?: string;
    cpu?: string;
    nmsVer?: string;
    kernel?: string;
    uptime?: number;
    cpuLoad?: number;
    memoryLoad?: number;
    swapLoad?: number;
    netCounters?: SystemNetCounters;
    memoryUsed?: number;
    memoryTotal?: number;
    hasUpdates?: boolean;
}

export interface HardwareSensor {
    name: string;
    type: 'temperature' | 'fan' | 'voltage' | 'other';
    value: number;
    unit: string;
}

export interface DashboardMetrics {
    pool: PoolStatus;
    disks: DiskItem[];
    networks: NetworkInterfaceItem[];
    services: RemoteServiceItem[];
    system: SystemInfo;
    sensors: HardwareSensor[];
}
