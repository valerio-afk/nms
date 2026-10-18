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
        if (isConfigured) {
            try {
                const capRes = await apiRequest<PropertyResponse<{ used: number; total: number }>>('/pool/get/pool_capacity');
                if (capRes?.value) {
                    capacity = capRes.value;
                }
            } catch {
                // capacity endpoint may fail if not mounted
            }
        }

        return { isConfigured, isMounted, capacity };
    } catch {
        return { isConfigured: false, isMounted: false, capacity: null };
    }
}

export async function fetchDisks(): Promise<DiskItem[]> {
    try {
        const res = await apiRequest<any[]>('/disks/get/disks');
        if (Array.isArray(res)) {
            return res.map(d => ({
                name: d.name || d.device || 'Disk',
                model: d.model,
                size: d.size,
                status: d.status || d.state || 'OK',
                temperature: d.temperature,
                inPool: !!d.in_pool
            }));
        }
        return [];
    } catch {
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
                }
            },
            disks: [
                { name: 'sda', model: 'Seagate IronWolf 4TB', size: 4000787030016, status: 'ONLINE', temperature: 34, inPool: true },
                { name: 'sdb', model: 'Seagate IronWolf 4TB', size: 4000787030016, status: 'ONLINE', temperature: 35, inPool: true },
                { name: 'nvme0n1', model: 'Samsung 980 Pro 500GB', size: 500107862016, status: 'OK', temperature: 41, inPool: false }
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
