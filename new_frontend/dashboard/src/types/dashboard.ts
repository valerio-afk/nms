export interface PoolCapacity {
    used: number;
    total: number;
}

export interface PoolStatus {
    isConfigured: boolean;
    isMounted: boolean;
    capacity: PoolCapacity | null;
}

export interface DiskItem {
    name: string;
    model?: string;
    size?: number;
    status: string;
    temperature?: number;
    inPool?: boolean;
}

export interface NetworkInterfaceItem {
    name: string;
    ipAddress?: string;
    status: 'up' | 'down';
    type: 'ethernet' | 'wifi' | 'vpn' | 'other';
    rxBytes?: number;
    txBytes?: number;
}

export interface RemoteServiceItem {
    id: string;
    name: string;
    active: boolean;
}

export interface SystemInfo {
    hostname?: string;
    os?: string;
    kernel?: string;
    uptime?: number;
    cpuLoad?: number;
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
