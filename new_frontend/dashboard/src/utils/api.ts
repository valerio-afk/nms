export * from '@nms/shared';
import { apiRequest } from '@nms/shared';
import type {
    DashboardMetrics,
    PoolStatus,
    DiskItem,
    NetworkInterfaceItem,
    NetworkIfaceType,
    RemoteServiceItem,
    SystemInfo,
    HardwareSensor,
    SnapshotItem,
    ScrubReport,
    ScrubInfo,
    ImportablePool,
    CreatePoolPayload,
    SmartInfo
} from '../types/dashboard';

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

export function mapRawDisk(d: any): DiskItem {
    const { statusCode, status } = parseDiskStatus(d.status ?? d.state);
    const physicalPaths = Array.isArray(d.physical_paths)
        ? d.physical_paths
        : (d.physical_paths ? [d.physical_paths] : (d.path ? [d.path] : []));

    return {
        name: d.name || d.device || 'Disk',
        model: d.model || '',
        serial: d.serial || d.serial_number || '',
        size: typeof d.size === 'number' ? d.size : null,
        status,
        statusCode,
        path: d.path || (d.name ? `/dev/${d.name}` : ''),
        physical_paths: physicalPaths,
        inPool: statusCode === 1,
        temperature: typeof d.temperature === 'number' ? d.temperature : undefined
    };
}

export async function fetchDisks(): Promise<DiskItem[]> {
    try {
        const res = await apiRequest<any>('/disks/get/disks');
        const items: any[] = Array.isArray(res) ? res : (Array.isArray(res?.value) ? res.value : []);
        return items.map(mapRawDisk);
    } catch (err) {
        console.error('Failed to fetch disks from /disks/get/disks:', err);
        return [];
    }
}

export async function fetchNetworks(): Promise<NetworkInterfaceItem[]> {
    try {
        const [ifacesRes, vpnRes] = await Promise.allSettled([
            apiRequest<any>('/net/ifaces'),
            apiRequest<any>('/net/vpn')
        ]);

        let rawIfaces: any[] = [];
        if (ifacesRes.status === 'fulfilled') {
            const val = ifacesRes.value;
            rawIfaces = Array.isArray(val) ? val : (Array.isArray(val?.value) ? val.value : []);
        }

        if (vpnRes.status === 'fulfilled' && vpnRes.value && typeof vpnRes.value === 'object') {
            const vpnData = vpnRes.value.value ?? vpnRes.value;
            if (vpnData && vpnData.name && !rawIfaces.some(i => i.name === vpnData.name)) {
                rawIfaces.push(vpnData);
            }
        }

        return rawIfaces.map((iface: any) => {
            const isEnabled = !!iface.enabled;
            const rawType = (iface.type || '').toLowerCase();
            const ifaceType: NetworkIfaceType =
                rawType === 'wifi' ? 'wifi' :
                rawType === 'vpn' ? 'vpn' :
                rawType === 'ethernet' ? 'ethernet' :
                (iface.name?.startsWith('wl') ? 'wifi' : iface.name?.startsWith('wg') || iface.name === 'vpn' ? 'vpn' : 'ethernet');

            const ipv4 = iface.ipv4 ? {
                dynamic: !!iface.ipv4.dynamic,
                address: iface.ipv4.address ? String(iface.ipv4.address) : null,
                netmask: iface.ipv4.netmask ? String(iface.ipv4.netmask) : null,
                gateway: iface.ipv4.gateway ? String(iface.ipv4.gateway) : null,
                dns: Array.isArray(iface.ipv4.dns) ? iface.ipv4.dns.map(String) : []
            } : null;

            const ipv6 = iface.ipv6 ? {
                enabled: !!iface.ipv6.enabled,
                dynamic: !!iface.ipv6.dynamic,
                address: iface.ipv6.address ? String(iface.ipv6.address) : null,
                netmask: iface.ipv6.netmask ? String(iface.ipv6.netmask) : null,
                gateway: iface.ipv6.gateway ? String(iface.ipv6.gateway) : null,
                dns: Array.isArray(iface.ipv6.dns) ? iface.ipv6.dns.map(String) : []
            } : null;

            const primaryIp = ipv4?.address || ipv6?.address || (typeof iface.ipAddress === 'string' ? iface.ipAddress : undefined);

            return {
                name: iface.name || iface.iface || 'Interface',
                enabled: isEnabled,
                network_name: iface.network_name || '',
                type: ifaceType,
                ipv4,
                ipv6,
                has_profile: !!iface.has_profile,
                ap: iface.ap ?? null,
                status: isEnabled ? 'up' : 'down',
                ipAddress: primaryIp,
                rxBytes: iface.rxBytes ?? iface.rx_bytes,
                txBytes: iface.txBytes ?? iface.tx_bytes
            };
        });
    } catch (err) {
        console.error('Failed to fetch network interfaces:', err);
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
            cpu: val.cpu,
            nmsVer: val.nms_ver,
            kernel: val.kernel || val.release,
            uptime: typeof val.uptime === 'number' ? val.uptime : (val.uptime ? Number(val.uptime) : undefined),
            cpuLoad: typeof val.cpu_load === 'number' ? val.cpu_load : (val.cpu_load ? Number(val.cpu_load) : undefined),
            memoryLoad: typeof val.memory_load === 'number' ? val.memory_load : (val.memory_load ? Number(val.memory_load) : undefined),
            swapLoad: typeof val.swap_load === 'number' ? val.swap_load : (val.swap_load ? Number(val.swap_load) : undefined),
            netCounters: val.net_counters ? {
                bytes_recv: Number(val.net_counters.bytes_recv || 0),
                bytes_sent: Number(val.net_counters.bytes_sent || 0),
                total_bytes_recv: Number(val.net_counters.total_bytes_recv || 0),
                total_bytes_sent: Number(val.net_counters.total_bytes_sent || 0)
            } : undefined,
            memoryUsed: val.memory_used || val.mem_used,
            memoryTotal: val.memory_total || val.mem_total,
            hasUpdates: !!val.updates
        };
    } catch (err) {
        console.error('Failed to fetch system info:', err);
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

// --- Disk & Pool Management Methods ---

export async function fetchAttachableDisks(): Promise<DiskItem[]> {
    try {
        const res = await apiRequest<any>('/pool/get/attachable-disks');
        const items: any[] = Array.isArray(res) ? res : (Array.isArray(res?.value) ? res.value : []);
        return items.map(mapRawDisk);
    } catch (err) {
        console.error('Failed to fetch attachable disks:', err);
        return [];
    }
}

export async function fetchImportablePools(): Promise<ImportablePool[]> {
    try {
        const res = await apiRequest<any>('/pool/get/pool_list');
        const items: any[] = Array.isArray(res) ? res : (Array.isArray(res?.value) ? res.value : []);
        return items.map((p: any) => ({
            name: p.name || 'Pool',
            state: p.state || 'ONLINE',
            disks: Array.isArray(p.disks) ? p.disks : [],
            message: p.message
        }));
    } catch (err) {
        console.error('Failed to fetch importable pools:', err);
        return [];
    }
}

export async function fetchScrubInfo(): Promise<ScrubInfo | null> {
    try {
        const res = await apiRequest<PropertyResponse<any>>('/pool/get/scrub_info');
        const val = res?.value;
        if (!val) return null;
        return {
            ongoing: !!val.ongoing,
            last: typeof val.last === 'number' ? val.last : null
        };
    } catch {
        return null;
    }
}

export async function fetchLastScrubReport(): Promise<ScrubReport | null> {
    try {
        const res = await apiRequest<PropertyResponse<any>>('/pool/get/last_scrub_report');
        const val = res?.value;
        if (!val) return null;
        return {
            started: val.started || '-',
            ended: val.ended || '-',
            errors: String(val.errors ?? '-')
        };
    } catch {
        return null;
    }
}

export async function fetchSnapshots(): Promise<SnapshotItem[]> {
    try {
        const res = await apiRequest<any>('/pool/get/snapshot');
        const items: any[] = Array.isArray(res) ? res : (Array.isArray(res?.value) ? res.value : []);
        return items.map((s: any) => {
            if (Array.isArray(s)) {
                return {
                    name: String(s[0] || ''),
                    ref_size: typeof s[1] === 'number' ? s[1] : 0
                };
            }
            return {
                name: String(s.name || ''),
                ref_size: typeof s.ref_size === 'number' ? s.ref_size : (typeof s.refSize === 'number' ? s.refSize : 0)
            };
        });
    } catch (err) {
        console.error('Failed to fetch snapshots:', err);
        return [];
    }
}

export async function mountPool(): Promise<void> {
    await apiRequest('/pool/mount', { method: 'POST' });
}

export async function unmountPool(): Promise<void> {
    await apiRequest('/pool/unmount', { method: 'POST' });
}

export async function startScrub(): Promise<void> {
    await apiRequest('/pool/scrub', { method: 'POST' });
}

export async function createSnapshot(name: string): Promise<void> {
    await apiRequest(`/pool/snapshot/${encodeURIComponent(name)}`, { method: 'POST' });
}

export async function deleteSnapshot(name: string): Promise<void> {
    await apiRequest(`/pool/snapshot/${encodeURIComponent(name)}`, { method: 'DELETE' });
}

export async function rollbackSnapshot(name: string): Promise<void> {
    await apiRequest(`/pool/snapshot/${encodeURIComponent(name)}`, { method: 'PATCH' });
}

export async function createPool(payload: CreatePoolPayload): Promise<void> {
    await apiRequest('/pool/create', {
        method: 'POST',
        body: JSON.stringify(payload)
    });
}

export async function expandPool(newDevice: string): Promise<void> {
    await apiRequest('/pool/expand', {
        method: 'POST',
        body: JSON.stringify({ new_device: newDevice })
    });
}

export async function formatDisk(dev: string): Promise<void> {
    await apiRequest(`/disks/format?dev=${encodeURIComponent(dev)}`, { method: 'POST' });
}

export async function fetchSmartInfo(dev: string): Promise<SmartInfo | null> {
    try {
        const res = await apiRequest<any>(`/disks/smart?dev=${encodeURIComponent(dev)}`);
        if (!res) return null;
        return {
            device: res.device || dev,
            available: !!res.available,
            enabled: !!res.enabled,
            passed: res.passed ?? null,
            poweron_time: res.poweron_time ?? null,
            temperature: typeof res.temperature === 'number' ? res.temperature : null,
            attributes: Array.isArray(res.attributes) ? res.attributes : [],
            self_test_logs: Array.isArray(res.self_test_logs) ? res.self_test_logs : []
        };
    } catch (err) {
        console.error(`Failed to fetch SMART info for ${dev}:`, err);
        return null;
    }
}

export async function runSmartTest(dev: string, testType: 'short' | 'long'): Promise<void> {
    await apiRequest(`/disks/smart/test/${testType}?dev=${encodeURIComponent(dev)}`, { method: 'POST' });
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
                {
                    name: 'eth0',
                    enabled: true,
                    status: 'up',
                    network_name: 'Wired connection 1',
                    type: 'ethernet',
                    ipAddress: '192.168.1.180',
                    has_profile: true,
                    ipv4: {
                        dynamic: true,
                        address: '192.168.1.180',
                        netmask: '255.255.255.0',
                        gateway: '192.168.1.1',
                        dns: ['1.1.1.1', '8.8.8.8']
                    },
                    ipv6: {
                        enabled: true,
                        dynamic: false,
                        address: 'fe80::1',
                        netmask: 'ffff:ffff:ffff:ffff::',
                        gateway: null,
                        dns: []
                    },
                    rxBytes: 154829012,
                    txBytes: 89324012
                },
                {
                    name: 'wlan0',
                    enabled: false,
                    status: 'down',
                    network_name: 'Home_WiFi_5G',
                    type: 'wifi',
                    ipAddress: '192.168.1.185',
                    has_profile: true,
                    ap: false,
                    ipv4: {
                        dynamic: true,
                        address: '192.168.1.185',
                        netmask: '255.255.255.0',
                        gateway: '192.168.1.1',
                        dns: ['1.1.1.1']
                    },
                    ipv6: null,
                    rxBytes: 1204012,
                    txBytes: 492012
                },
                {
                    name: 'vpn',
                    enabled: true,
                    status: 'up',
                    network_name: 'VPN',
                    type: 'vpn',
                    ipAddress: '10.8.0.2',
                    has_profile: false,
                    ipv4: {
                        dynamic: false,
                        address: '10.8.0.2',
                        netmask: '255.255.255.0',
                        gateway: null,
                        dns: []
                    },
                    ipv6: null
                }
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
                cpu: 'Intel(R) Core(TM) i7-10700 with 16 core(s)',
                nmsVer: '0.1rc1',
                kernel: 'Linux 6.8.0-31-generic',
                uptime: Math.floor(Date.now() / 1000) - 432890,
                cpuLoad: 14,
                memoryLoad: 42,
                swapLoad: 4,
                netCounters: {
                    bytes_recv: 1245000,
                    bytes_sent: 450000,
                    total_bytes_recv: 8593812000,
                    total_bytes_sent: 3491823000
                },
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

    const [poolRes, disksRes, networksRes, servicesRes, systemRes, sensorsRes] = await Promise.allSettled([
        fetchPoolStatus(),
        fetchDisks(),
        fetchNetworks(),
        fetchServices(),
        fetchSystemInfo(),
        fetchSensors()
    ]);

    return {
        pool: poolRes.status === 'fulfilled' ? poolRes.value : { isConfigured: false, isMounted: false, capacity: null },
        disks: disksRes.status === 'fulfilled' ? disksRes.value : [],
        networks: networksRes.status === 'fulfilled' ? networksRes.value : [],
        services: servicesRes.status === 'fulfilled' ? servicesRes.value : [],
        system: systemRes.status === 'fulfilled' ? systemRes.value : {},
        sensors: sensorsRes.status === 'fulfilled' ? sensorsRes.value : []
    };
}
