export * from '@nms/shared';
import { apiRequest } from '@nms/shared';
import type { DashboardMetrics, PoolStatus, DiskItem, NetworkInterfaceItem, RemoteServiceItem, SystemInfo, HardwareSensor } from '../types/dashboard';

interface PropertyResponse<T> {
    property: string;
    value: T;
}

export async function fetchPoolStatus(): Promise<PoolStatus> {
    try {
        const [confRes, mountedRes] = await Promise.allSettled([
            apiRequest<PropertyResponse<boolean>>('/pool/get/is_configured'),
            apiRequest<PropertyResponse<boolean>>('/pool/get/is_mounted')
        ]);

        const isConfigured = confRes.status === 'fulfilled' ? !!confRes.value.value : false;
        const isMounted = mountedRes.status === 'fulfilled' ? !!mountedRes.value.value : false;

        let capacity: { used: number; total: number } | null = null;
        let settings = null;

        if (isConfigured) {
            const [capRes, setRes] = await Promise.allSettled([
                apiRequest<PropertyResponse<{ used: number; total: number }>>('/pool/get/pool_capacity'),
                apiRequest<PropertyResponse<{ encryption: boolean; redundancy: boolean; compression: boolean }>>('/pool/get/pool_settings')
            ]);
            if (capRes.status === 'fulfilled' && capRes.value?.value) {
                capacity = capRes.value.value;
            }
            if (setRes.status === 'fulfilled' && setRes.value?.value) {
                settings = setRes.value.value;
            }
        }

        return { isConfigured, isMounted, capacity, settings };
    } catch {
        return { isConfigured: false, isMounted: false, capacity: null, settings: null };
    }
}

export function parseDiskStatus(statusRaw: any): { statusCode: number; status: 'ONLINE' | 'NEW' | 'OFFLINE' | 'CORRUPTED' | 'UNKNOWN' } {
    let code: number;
    if (typeof statusRaw === 'number') {
        code = statusRaw;
    } else if (typeof statusRaw === 'string') {
        const s = statusRaw.toUpperCase();
        if (s === 'ONLINE' || s === 'OK') code = 1;
        else if (s === 'NEW') code = 0;
        else if (s === 'OFFLINE' || s === 'UNAVAIL') code = -1;
        else if (s === 'CORRUPTED' || s === 'DEGRADED' || s === 'FAULTED') code = -2;
        else code = -3;
    } else {
        code = -3;
    }

    switch (code) {
        case 1:
            return { statusCode: 1, status: 'ONLINE' };
        case 0:
            return { statusCode: 0, status: 'NEW' };
        case -1:
            return { statusCode: -1, status: 'OFFLINE' };
        case -2:
            return { statusCode: -2, status: 'CORRUPTED' };
        default:
            return { statusCode: -3, status: 'UNKNOWN' };
    }
}

export async function fetchDisks(): Promise<DiskItem[]> {
    try {
        const res = await apiRequest<any>('/disks/get/disks');
        const items: any[] = Array.isArray(res) ? res : (Array.isArray(res?.value) ? res.value : []);

        return items.map((d: any) => {
            const { statusCode, status } = parseDiskStatus(d.status ?? d.state);
            return {
                name: d.name || d.device || 'Disk',
                model: d.model || '',
                serial: d.serial || d.serial_number || '',
                size: typeof d.size === 'number' ? d.size : null,
                status,
                statusCode,
                path: d.path || (d.name ? `/dev/${d.name}` : ''),
                inPool: statusCode === 1,
                temperature: typeof d.temperature === 'number' ? d.temperature : undefined
            };
        });
    } catch (err) {
        console.error('Failed to fetch disks from /disks/get/disks:', err);
        return [];
    }
}

export async function fetchNetworks(): Promise<NetworkInterfaceItem[]> {
    try {
        const res = await apiRequest<any[]>('/net/ifaces');
        if (Array.isArray(res)) {
            return res.map(iface => ({
                name: iface.name || iface.iface,
                ipAddress: iface.ipv4?.address || iface.ip || iface.address,
                status: iface.is_up || iface.up || iface.active ? 'up' : 'down',
                type: iface.name?.startsWith('wl') ? 'wifi' : iface.name?.startsWith('wg') ? 'vpn' : 'ethernet',
                rxBytes: iface.rx_bytes,
                txBytes: iface.tx_bytes
            }));
        }
        return [];
    } catch {
        return [];
    }
}

export async function fetchServices(): Promise<RemoteServiceItem[]> {
    try {
        const res = await apiRequest<Record<string, any>>('/services/get');
        if (res && typeof res === 'object') {
            return Object.entries(res).map(([id, s]) => ({
                id,
                name: (s.name || id).toUpperCase(),
                active: !!s.active
            }));
        }
        return [];
    } catch {
        return [];
    }
}

export async function fetchSystemInfo(): Promise<SystemInfo> {
    try {
        const res = await apiRequest<PropertyResponse<any>>('/system/get/system_information');
        const val = res?.value || {};
        return {
            hostname: val.hostname || val.nodename,
            os: val.os || val.distribution || val.sysname,
            kernel: val.kernel || val.release,
            uptime: typeof val.uptime === 'number' ? val.uptime : undefined,
            cpuLoad: val.cpu_load || val.load,
            memoryUsed: val.memory_used || val.mem_used,
            memoryTotal: val.memory_total || val.mem_total,
            hasUpdates: !!val.updates
        };
    } catch {
        return {};
    }
}

export async function fetchSensors(): Promise<HardwareSensor[]> {
    try {
        const res = await apiRequest<any[]>('/system/sensors');
        if (Array.isArray(res)) {
            return res.map(s => ({
                name: s.name || s.label || 'Sensor',
                type: s.type || (s.unit === '°C' ? 'temperature' : s.unit === 'RPM' ? 'fan' : 'other'),
                value: s.value ?? s.temp ?? 0,
                unit: s.unit || '°C'
            }));
        }
        return [];
    } catch {
        return [];
    }
}

export async function rebootSystem(): Promise<void> {
    await apiRequest('/system/restart', { method: 'POST' });
}

export async function shutdownSystem(): Promise<void> {
    await apiRequest('/system/shutdown', { method: 'POST' });
}

export async function fetchDashboardMetrics(): Promise<DashboardMetrics> {
    const isDemo = typeof window !== 'undefined' && window.location.search.includes('demo=true');

    if (isDemo) {
        return {
            pool: {
                isConfigured: true,
                isMounted: true,
                capacity: {
                    used: 3435973836800,
                    total: 8000000000000
                },
                settings: {
                    encryption: false,
                    redundancy: true,
                    compression: true
                }
            },
            disks: [
                { name: 'sda', model: 'Seagate IronWolf 4TB', serial: 'W123456', size: 4000787030016, status: 'ONLINE', statusCode: 1, path: '/dev/sda', inPool: true, temperature: 34 },
                { name: 'sdb', model: 'Seagate IronWolf 4TB', serial: 'W123457', size: 4000787030016, status: 'ONLINE', statusCode: 1, path: '/dev/sdb', inPool: true, temperature: 35 },
                { name: 'nvme0n1', model: 'Samsung 980 Pro 500GB', serial: 'S980PRO', size: 500107862016, status: 'NEW', statusCode: 0, path: '/dev/nvme0n1', inPool: false, temperature: 41 }
            ],
            networks: [
                { name: 'eth0', ipAddress: '192.168.1.180', status: 'up', type: 'ethernet', rxBytes: 154829012, txBytes: 89324012 },
                { name: 'wlan0', ipAddress: '192.168.1.185', status: 'up', type: 'wifi', rxBytes: 1204012, txBytes: 492012 },
                { name: 'wg0', ipAddress: '10.8.0.1', status: 'up', type: 'vpn' }
            ],
            services: [
                { id: 'ssh', name: 'SSH', active: true },
                { id: 'samba', name: 'SAMBA', active: true },
                { id: 'sftp', name: 'SFTP', active: true },
                { id: 'webdav', name: 'WEBDAV', active: false }
            ],
            system: {
                hostname: 'nms-node-01',
                os: 'Ubuntu 24.04 LTS',
                kernel: 'Linux 6.8.0-31-generic',
                uptime: 432890,
                cpuLoad: 14.5,
                memoryUsed: 4294967296,
                memoryTotal: 17179869184,
                hasUpdates: false
            },
            sensors: [
                { name: 'CPU Core 0', type: 'temperature', value: 42, unit: '°C' },
                { name: 'CPU Core 1', type: 'temperature', value: 41, unit: '°C' },
                { name: 'System Fan 1', type: 'fan', value: 1250, unit: 'RPM' },
                { name: 'System Fan 2', type: 'fan', value: 1180, unit: 'RPM' }
            ]
        };
    }

    const [pool, disks, networks, services, system, sensors] = await Promise.all([
        fetchPoolStatus(),
        fetchDisks(),
        fetchNetworks(),
        fetchServices(),
        fetchSystemInfo(),
        fetchSensors()
    ]);

    return {
        pool,
        disks,
        networks,
        services,
        system,
        sensors
    };
}
