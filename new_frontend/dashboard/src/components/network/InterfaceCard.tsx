import { useState, useEffect } from 'react';
import {
    Network,
    Wifi,
    Radio,
    ArrowDown,
    ArrowUp,
    CheckCircle2,
    XCircle,
    Power,
    Lock,
    Eye,
    EyeOff,
    RotateCw,
    ChevronDown,
    ChevronUp
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { NetworkInterfaceItem } from '../../types/dashboard';
import type { WifiNetworkItem } from '../../types/network';
import { fetchWifiNetworks } from '../../utils/api';
import { formatBytes } from '../../utils/formatters';

interface InterfaceCardProps {
    iface: NetworkInterfaceItem;
    onToggleStatus: (ifaceName: string, action: 'up' | 'down') => Promise<void>;
    onConnectWifi?: (ifaceName: string, ssid: string, psk?: string | null, profile?: string | null) => Promise<void>;
    onEnableHotspot?: (ifaceName: string, ssid: string, psk?: string | null) => Promise<void>;
    isLoading?: boolean;
}

function SignalStrengthBars({ strength }: { strength: number }) {
    return (
        <span className="inline-flex items-end gap-0.5 h-3.5" title={`Signal: ${strength}/4`}>
            <span className={`w-1 rounded-xs transition-colors ${strength >= 1 ? 'h-1.5 bg-emerald-500' : 'h-1.5 bg-gray-300 dark:bg-zinc-700'}`} />
            <span className={`w-1 rounded-xs transition-colors ${strength >= 2 ? 'h-2 bg-emerald-500' : 'h-2 bg-gray-300 dark:bg-zinc-700'}`} />
            <span className={`w-1 rounded-xs transition-colors ${strength >= 3 ? 'h-2.5 bg-emerald-500' : 'h-2.5 bg-gray-300 dark:bg-zinc-700'}`} />
            <span className={`w-1 rounded-xs transition-colors ${strength >= 4 ? 'h-3.5 bg-emerald-500' : 'h-3.5 bg-gray-300 dark:bg-zinc-700'}`} />
        </span>
    );
}

export default function InterfaceCard({
    iface,
    onToggleStatus,
    onConnectWifi,
    onEnableHotspot,
    isLoading = false
}: InterfaceCardProps) {
    const { t } = useTranslation();
    const [actionLoading, setActionLoading] = useState(false);

    const isUp = iface.status === 'up' && iface.enabled;
    const isWifi = iface.type === 'wifi';
    const isHotspot = !!iface.ap;

    // Wi-Fi Scanning & Connection State
    const [wifiNetworks, setWifiNetworks] = useState<WifiNetworkItem[]>([]);
    const [isScanning, setIsScanning] = useState(false);
    const [selectedSsid, setSelectedSsid] = useState<string>('');
    const [isCustomSsid, setIsCustomSsid] = useState(false);
    const [customSsid, setCustomSsid] = useState('');
    const [psk, setPsk] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);

    // Hotspot Drawer State
    const [showHotspotDrawer, setShowHotspotDrawer] = useState(false);
    const [hotspotSsid, setHotspotSsid] = useState('NMS');
    const [hotspotPsk, setHotspotPsk] = useState('password123');
    const [isEnablingHotspot, setIsEnablingHotspot] = useState(false);

    const handleScanWifi = async () => {
        if (!isWifi) return;
        setIsScanning(true);
        try {
            const list = await fetchWifiNetworks(iface.name);
            setWifiNetworks(list);
            const connectedNet = list.find(n => n.connected && n.ssid);
            if (connectedNet?.ssid) {
                setSelectedSsid(connectedNet.ssid);
            } else if (list.length > 0 && list[0].ssid) {
                setSelectedSsid(list[0].ssid);
            }
        } finally {
            setIsScanning(false);
        }
    };

    // Auto-scan Wi-Fi networks when component mounts if it's a Wi-Fi adapter
    useEffect(() => {
        if (isWifi) {
            handleScanWifi();
        }
    }, [isWifi, iface.name]);

    const handleToggle = async () => {
        setActionLoading(true);
        try {
            await onToggleStatus(iface.name, isUp ? 'down' : 'up');
        } finally {
            setActionLoading(false);
        }
    };

    const handleConnectSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const targetSsid = isCustomSsid ? customSsid.trim() : selectedSsid.trim();
        if (!targetSsid || !onConnectWifi) return;

        setIsConnecting(true);
        try {
            const profile = iface.has_profile ? (iface.network_name || null) : null;
            await onConnectWifi(iface.name, targetSsid, psk.trim() || null, profile);
            setPsk('');
            await handleScanWifi();
        } finally {
            setIsConnecting(false);
        }
    };

    const handleHotspotSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!hotspotSsid.trim() || !onEnableHotspot) return;

        setIsEnablingHotspot(true);
        try {
            await onEnableHotspot(iface.name, hotspotSsid.trim(), hotspotPsk.trim() || null);
            setShowHotspotDrawer(false);
        } finally {
            setIsEnablingHotspot(false);
        }
    };

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 transition-all hover:shadow-md space-y-5">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                <div className="flex items-center gap-3">
                    <div className={`p-2.5 rounded-xl ${
                        isUp
                            ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400'
                            : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-500'
                    }`}>
                        {isHotspot ? (
                            <Radio className="w-5 h-5" />
                        ) : isWifi ? (
                            <Wifi className="w-5 h-5" />
                        ) : (
                            <Network className="w-5 h-5" />
                        )}
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <h3 className="text-base font-bold text-gray-900 dark:text-white">
                                {iface.name}
                            </h3>
                            <span className="text-xs px-2 py-0.5 rounded-md font-mono bg-gray-100 dark:bg-zinc-800 text-gray-600 dark:text-zinc-400">
                                {isHotspot
                                    ? t('widgets.network.hotspot', 'Hotspot')
                                    : isWifi
                                        ? t('widgets.network.wifi', 'Wi-Fi')
                                        : t('widgets.network.ethernet', 'Ethernet')}
                            </span>
                        </div>
                        {iface.network_name && (
                            <p className="text-xs text-gray-500 dark:text-zinc-400 mt-0.5">
                                {iface.network_name}
                            </p>
                        )}
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
                        isUp
                            ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/50'
                            : 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-700'
                    }`}>
                        {isUp ? (
                            <>
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                <span>{t('network_page.status_up', 'Active')}</span>
                            </>
                        ) : (
                            <>
                                <XCircle className="w-3.5 h-3.5 text-zinc-400" />
                                <span>{t('network_page.status_down', 'Disconnected')}</span>
                            </>
                        )}
                    </span>

                    <button
                        type="button"
                        onClick={handleToggle}
                        disabled={isLoading || actionLoading}
                        title={isUp ? t('network_page.disable_iface', 'Disconnect') : t('network_page.enable_iface', 'Connect')}
                        className={`p-2 rounded-xl border transition-all cursor-pointer ${
                            isUp
                                ? 'bg-red-50 hover:bg-red-100 border-red-200 text-red-600 dark:bg-red-950/40 dark:hover:bg-red-950/60 dark:border-red-900/50 dark:text-red-400'
                                : 'bg-emerald-50 hover:bg-emerald-100 border-emerald-200 text-emerald-600 dark:bg-emerald-950/40 dark:hover:bg-emerald-950/60 dark:border-emerald-900/50 dark:text-emerald-400'
                        } disabled:opacity-50`}
                    >
                        <Power className={`w-4 h-4 ${actionLoading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {/* IPv4 Configuration */}
            {iface.ipv4 && (
                <div className="p-4 rounded-xl bg-gray-50/70 dark:bg-zinc-800/40 border border-gray-100 dark:border-zinc-800 space-y-2.5 text-xs">
                    <div className="flex items-center justify-between">
                        <span className="font-semibold text-gray-900 dark:text-zinc-200 flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-indigo-500" />
                            {t('network_page.ipv4', 'IPv4')}
                        </span>
                        <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 text-gray-600 dark:text-zinc-300">
                            {iface.ipv4.dynamic
                                ? t('network_page.dynamic_dhcp', 'DHCP (Dynamic)')
                                : t('network_page.static_ip', 'Static IP')}
                        </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1 font-mono">
                        <div>
                            <span className="text-[10px] uppercase text-gray-400 dark:text-zinc-500 block">
                                {t('network_page.address', 'Address')}
                            </span>
                            <span className="font-semibold text-gray-800 dark:text-zinc-100">
                                {iface.ipv4.address || '-'}
                            </span>
                        </div>
                        <div>
                            <span className="text-[10px] uppercase text-gray-400 dark:text-zinc-500 block">
                                {t('network_page.netmask', 'Subnet')}
                            </span>
                            <span className="text-gray-700 dark:text-zinc-300">
                                {iface.ipv4.netmask || '-'}
                            </span>
                        </div>
                        <div>
                            <span className="text-[10px] uppercase text-gray-400 dark:text-zinc-500 block">
                                {t('network_page.gateway', 'Gateway')}
                            </span>
                            <span className="text-gray-700 dark:text-zinc-300">
                                {iface.ipv4.gateway || '-'}
                            </span>
                        </div>
                    </div>

                    {iface.ipv4.dns && iface.ipv4.dns.length > 0 && (
                        <div className="pt-1 border-t border-gray-200/50 dark:border-zinc-700/50 flex items-center gap-2 text-[11px]">
                            <span className="text-gray-400 dark:text-zinc-500 font-mono">
                                {t('network_page.dns', 'DNS')}:
                            </span>
                            <span className="font-mono text-gray-700 dark:text-zinc-300">
                                {iface.ipv4.dns.join(', ')}
                            </span>
                        </div>
                    )}
                </div>
            )}

            {/* IPv6 Configuration (if present) */}
            {iface.ipv6 && iface.ipv6.address && (
                <div className="p-4 rounded-xl bg-gray-50/70 dark:bg-zinc-800/40 border border-gray-100 dark:border-zinc-800 space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                        <span className="font-semibold text-gray-900 dark:text-zinc-200 flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-purple-500" />
                            {t('network_page.ipv6', 'IPv6')}
                        </span>
                    </div>
                    <div className="font-mono text-gray-800 dark:text-zinc-200 break-all">
                        {iface.ipv6.address}
                    </div>
                </div>
            )}

            {/* Wi-Fi Setup Section (Only for Wi-Fi Adapters) */}
            {isWifi && (
                <div className="border border-indigo-100 dark:border-indigo-950/60 rounded-xl p-4 bg-indigo-50/30 dark:bg-indigo-950/10 space-y-4 text-xs">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Wifi className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                            <span className="font-bold text-gray-900 dark:text-white">
                                {t('network_page.wifi_setup', 'Wi-Fi Networks')}
                            </span>
                        </div>

                        <button
                            type="button"
                            onClick={handleScanWifi}
                            disabled={isScanning}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-semibold text-indigo-700 dark:text-indigo-300 bg-white dark:bg-zinc-800 border border-indigo-200 dark:border-indigo-900/50 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 transition-colors cursor-pointer disabled:opacity-50"
                        >
                            <RotateCw className={`w-3 h-3 ${isScanning ? 'animate-spin' : ''}`} />
                            <span>{isScanning ? t('network_page.scanning', 'Scanning...') : t('network_page.scan_networks', 'Scan')}</span>
                        </button>
                    </div>

                    <form onSubmit={handleConnectSubmit} className="space-y-3">
                        {/* Scanned Networks List */}
                        <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                            {wifiNetworks.map((net, idx) => {
                                const ssid = net.ssid || net.bssid;
                                const isSelected = !isCustomSsid && selectedSsid === ssid;
                                return (
                                    <label
                                        key={net.bssid || idx}
                                        className={`flex items-center justify-between p-2.5 rounded-lg border cursor-pointer transition-colors ${
                                            isSelected
                                                ? 'bg-indigo-50 dark:bg-indigo-950/50 border-indigo-300 dark:border-indigo-800'
                                                : 'bg-white dark:bg-zinc-800/60 border-gray-200 dark:border-zinc-700 hover:bg-gray-50 dark:hover:bg-zinc-800'
                                        }`}
                                    >
                                        <div className="flex items-center gap-2.5">
                                            <input
                                                type="radio"
                                                name={`wifi-${iface.name}`}
                                                checked={isSelected}
                                                onChange={() => {
                                                    setIsCustomSsid(false);
                                                    setSelectedSsid(ssid);
                                                }}
                                                className="text-indigo-600 focus:ring-indigo-500"
                                            />
                                            <span className="font-semibold text-gray-900 dark:text-zinc-100">
                                                {net.ssid || net.bssid}
                                            </span>
                                            {net.connected && (
                                                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/50">
                                                    {t('network_page.connected', 'Connected')}
                                                </span>
                                            )}
                                        </div>

                                        <div className="flex items-center gap-2">
                                            {net.security && net.security.toLowerCase() !== 'none' && (
                                                <span title={net.security}>
                                                    <Lock className="w-3.5 h-3.5 text-amber-500" />
                                                </span>
                                            )}
                                            <SignalStrengthBars strength={net.strength} />
                                        </div>
                                    </label>
                                );
                            })}

                            {/* Hidden / Manual Network Option */}
                            <label className={`flex items-center gap-2.5 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                                isCustomSsid
                                    ? 'bg-indigo-50 dark:bg-indigo-950/50 border-indigo-300 dark:border-indigo-800'
                                    : 'bg-white dark:bg-zinc-800/60 border-gray-200 dark:border-zinc-700 hover:bg-gray-50 dark:hover:bg-zinc-800'
                            }`}>
                                <input
                                    type="radio"
                                    name={`wifi-${iface.name}`}
                                    checked={isCustomSsid}
                                    onChange={() => setIsCustomSsid(true)}
                                    className="text-indigo-600 focus:ring-indigo-500"
                                />
                                <span className="font-medium text-gray-700 dark:text-zinc-300">
                                    {t('network_page.hidden_network', 'Connect to Hidden / Other Network')}
                                </span>
                            </label>
                        </div>

                        {/* Custom SSID Input if chosen */}
                        {isCustomSsid && (
                            <div>
                                <input
                                    type="text"
                                    value={customSsid}
                                    onChange={e => setCustomSsid(e.target.value)}
                                    placeholder={t('network_page.custom_ssid_placeholder', 'Enter network name (SSID) manually')}
                                    className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                                />
                            </div>
                        )}

                        {/* Password / PSK Input */}
                        <div className="flex gap-2">
                            <div className="relative flex-1">
                                <input
                                    type={showPassword ? 'text' : 'password'}
                                    value={psk}
                                    onChange={e => setPsk(e.target.value)}
                                    placeholder={t('network_page.password_placeholder', 'Enter password if required')}
                                    className="w-full px-3 py-2 pr-9 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="absolute right-2.5 top-2.5 text-gray-400 hover:text-gray-600 dark:hover:text-zinc-200 cursor-pointer"
                                    title={showPassword ? 'Hide password' : 'Show password'}
                                >
                                    {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                                </button>
                            </div>

                            <button
                                type="submit"
                                disabled={isConnecting || (!isCustomSsid && !selectedSsid) || (isCustomSsid && !customSsid.trim())}
                                className="px-4 py-2 rounded-xl font-semibold text-xs text-white bg-indigo-600 hover:bg-indigo-500 shadow-sm cursor-pointer disabled:opacity-50 transition-colors"
                            >
                                {isConnecting ? t('network_page.connecting', 'Connecting...') : t('network_page.connect_button', 'Connect')}
                            </button>
                        </div>
                    </form>

                    {/* Wi-Fi Hotspot Drawer Toggle */}
                    <div className="pt-2 border-t border-indigo-100 dark:border-indigo-950/60">
                        <button
                            type="button"
                            onClick={() => setShowHotspotDrawer(!showHotspotDrawer)}
                            className="w-full flex items-center justify-between text-[11px] font-semibold text-indigo-700 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 cursor-pointer py-1"
                        >
                            <span className="flex items-center gap-1.5">
                                <Radio className="w-3.5 h-3.5" />
                                {t('network_page.hotspot_title', 'Wi-Fi Hotspot (Access Point)')}
                            </span>
                            {showHotspotDrawer ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </button>

                        {showHotspotDrawer && (
                            <form onSubmit={handleHotspotSubmit} className="mt-3 p-3 rounded-lg bg-white dark:bg-zinc-800/80 border border-indigo-100 dark:border-indigo-900/40 space-y-3 text-xs animate-in fade-in duration-100">
                                <p className="text-[11px] text-gray-500 dark:text-zinc-400 leading-relaxed">
                                    {t('network_page.hotspot_desc', 'Broadcast a Wi-Fi network directly from this NAS to connect without an external router.')}
                                </p>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                    <div>
                                        <label className="block text-[10px] uppercase font-semibold text-gray-500 dark:text-zinc-400 mb-1">
                                            {t('network_page.hotspot_ssid', 'Hotspot Name')}
                                        </label>
                                        <input
                                            type="text"
                                            value={hotspotSsid}
                                            onChange={e => setHotspotSsid(e.target.value)}
                                            className="w-full px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-[10px] uppercase font-semibold text-gray-500 dark:text-zinc-400 mb-1">
                                            {t('network_page.hotspot_psk', 'Hotspot Password')}
                                        </label>
                                        <input
                                            type="text"
                                            value={hotspotPsk}
                                            onChange={e => setHotspotPsk(e.target.value)}
                                            className="w-full px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs"
                                        />
                                    </div>
                                </div>

                                <div className="flex justify-end pt-1">
                                    <button
                                        type="submit"
                                        disabled={isEnablingHotspot || !hotspotSsid.trim()}
                                        className="px-3 py-1.5 rounded-lg font-semibold text-xs text-white bg-indigo-600 hover:bg-indigo-500 shadow-xs cursor-pointer disabled:opacity-50"
                                    >
                                        {isEnablingHotspot ? t('common.saving', 'Enabling...') : t('network_page.enable_hotspot', 'Start Hotspot')}
                                    </button>
                                </div>
                            </form>
                        )}
                    </div>
                </div>
            )}

            {/* Traffic Throughput */}
            {(typeof iface.rxBytes === 'number' || typeof iface.txBytes === 'number') && (
                <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-zinc-800/80 text-xs">
                    <span className="text-gray-500 dark:text-zinc-400">
                        {t('network_page.traffic', 'Traffic')}
                    </span>
                    <div className="flex items-center gap-4 font-mono text-[11px]">
                        <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                            <ArrowDown className="w-3.5 h-3.5" />
                            <span>{formatBytes(iface.rxBytes ?? 0)}</span>
                        </span>
                        <span className="flex items-center gap-1 text-sky-600 dark:text-sky-400">
                            <ArrowUp className="w-3.5 h-3.5" />
                            <span>{formatBytes(iface.txBytes ?? 0)}</span>
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
}
