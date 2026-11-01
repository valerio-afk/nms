import { useState } from 'react';
import { Network, Wifi, Shield, ChevronDown, Radio, Globe, AlertTriangle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { NetworkInterfaceItem } from '../../types/dashboard';

interface NetworkOverviewWidgetProps {
    networks: NetworkInterfaceItem[];
    onNavigateToNetwork?: () => void;
}

export default function NetworkOverviewWidget({ networks, onNavigateToNetwork }: NetworkOverviewWidgetProps) {
    const { t } = useTranslation();
    const [expandedIfaces, setExpandedIfaces] = useState<Record<string, boolean>>({});

    const toggleExpand = (name: string) => {
        setExpandedIfaces(prev => ({ ...prev, [name]: !prev[name] }));
    };

    const activeCount = networks.filter(n => n.enabled || n.status === 'up').length;

    const getIfaceIcon = (iface: NetworkInterfaceItem) => {
        if (iface.type === 'wifi') {
            if (iface.ap) {
                return <Radio className="w-4 h-4 text-amber-500 shrink-0" />;
            }
            return <Wifi className="w-4 h-4 text-sky-500 shrink-0" />;
        }
        if (iface.type === 'vpn') {
            return <Shield className="w-4 h-4 text-emerald-500 shrink-0" />;
        }
        return <Network className="w-4 h-4 text-indigo-500 shrink-0" />;
    };

    const getIfaceCharm = (iface: NetworkInterfaceItem) => {
        if (iface.type === 'wifi') return iface.ap ? '📡' : '🛜';
        if (iface.type === 'vpn') return '🛡️';
        return '🔌';
    };

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 flex flex-col justify-between transition-all hover:shadow-md">
            <div>
                {/* Header */}
                <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-sky-50 dark:bg-sky-950/40 text-sky-600 dark:text-sky-400">
                            <Globe className="w-5 h-5" />
                        </div>
                        <div>
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                                {t('widgets.network.title', 'Network Interfaces')}
                            </h3>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {activeCount} / {networks.length} {t('widgets.network.active', 'Active')}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Interfaces List */}
                <div className="mt-4 space-y-2 max-h-72 overflow-y-auto pr-1">
                    {networks.length === 0 ? (
                        <div className="p-4 my-2 rounded-xl border border-amber-200 bg-amber-50/80 dark:bg-amber-950/30 dark:border-amber-800/50 text-amber-700 dark:text-amber-400 text-xs flex items-center gap-2.5">
                            <AlertTriangle className="w-4 h-4 shrink-0" />
                            <span className="font-medium">{t('widgets.network.no_interfaces', 'No network interfaces detected.')}</span>
                        </div>
                    ) : (
                        networks.map((net) => {
                            const isExpanded = !!expandedIfaces[net.name];
                            const isEnabled = net.enabled || net.status === 'up';
                            const charm = getIfaceCharm(net);

                            return (
                                <div
                                    key={net.name}
                                    className="rounded-xl border border-gray-100 dark:border-zinc-800/80 bg-gray-50/70 dark:bg-zinc-800/50 transition-all overflow-hidden"
                                >
                                    {/* Interface summary row */}
                                    <button
                                        type="button"
                                        onClick={() => toggleExpand(net.name)}
                                        className="w-full flex items-center justify-between p-3 text-left hover:bg-gray-100/60 dark:hover:bg-zinc-800/80 transition-colors cursor-pointer"
                                        aria-expanded={isExpanded}
                                    >
                                        <div className="flex items-center gap-2.5 min-w-0 pr-2">
                                            <div className="p-1.5 rounded-lg bg-white dark:bg-zinc-800 border border-gray-200/60 dark:border-zinc-700/60 shadow-2xs">
                                                {getIfaceIcon(net)}
                                            </div>

                                            <div className="min-w-0">
                                                <div className="flex items-center gap-1.5 flex-wrap">
                                                    <span className="text-xs font-mono font-semibold text-gray-900 dark:text-white">
                                                        {net.name}
                                                    </span>
                                                    {net.network_name && (
                                                        <span className="text-[11px] text-gray-500 dark:text-zinc-400 truncate max-w-[140px]" title={net.network_name}>
                                                            ({net.network_name})
                                                        </span>
                                                    )}
                                                    {net.ap && (
                                                        <span className="px-1.5 py-0.2 rounded text-[10px] font-medium bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-400">
                                                            {t('widgets.network.hotspot', 'Hotspot')}
                                                        </span>
                                                    )}
                                                </div>

                                                <p className="text-[11px] font-mono text-gray-500 dark:text-zinc-400 truncate">
                                                    {net.ipAddress || (net.ipv4?.address ? net.ipv4.address : '—')}
                                                </p>
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-2 shrink-0">
                                            <span
                                                className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md border ${
                                                    isEnabled
                                                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-400 dark:border-emerald-800/40'
                                                        : 'bg-zinc-100 text-zinc-600 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:border-zinc-700'
                                                }`}
                                            >
                                                <span>{charm}</span>
                                                <span>{isEnabled ? t('widgets.network.enabled', 'Enabled') : t('widgets.network.disabled', 'Disabled')}</span>
                                            </span>

                                            <ChevronDown
                                                className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${
                                                    isExpanded ? 'rotate-180' : ''
                                                }`}
                                            />
                                        </div>
                                    </button>

                                    {/* Expanded Details */}
                                    {isExpanded && (
                                        <div className="px-3.5 pb-3 pt-1 border-t border-gray-100 dark:border-zinc-800/70 text-xs space-y-2.5 animate-in fade-in-50 duration-150">
                                            {net.network_name && (
                                                <div className="flex justify-between items-center py-1 border-b border-gray-100 dark:border-zinc-800/50">
                                                    <span className="font-medium text-gray-500 dark:text-zinc-400">
                                                        {t('widgets.network.network_name', 'Network')}:
                                                    </span>
                                                    <span className="font-semibold text-gray-800 dark:text-zinc-200">
                                                        {net.network_name}
                                                    </span>
                                                </div>
                                            )}

                                            {/* IPv4 Details */}
                                            {net.ipv4 && (
                                                <div className="space-y-1.5 pt-0.5">
                                                    <div className="flex items-center justify-between">
                                                        <span className="font-semibold text-gray-700 dark:text-zinc-300 text-[11px] uppercase tracking-wide">
                                                            {t('widgets.network.ipv4_address', 'IPv4 Address')}
                                                        </span>
                                                        {net.name !== 'vpn' && (
                                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-200/60 dark:bg-zinc-700/60 text-gray-600 dark:text-zinc-300">
                                                                {t('widgets.network.dynamic_ip', 'Dynamic IP')}:{' '}
                                                                <strong className={net.ipv4.dynamic ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-700 dark:text-zinc-300'}>
                                                                    {net.ipv4.dynamic ? t('widgets.network.enabled', 'Enabled') : t('widgets.network.disabled', 'Disabled')}
                                                                </strong>
                                                            </span>
                                                        )}
                                                    </div>

                                                    <div className="bg-white/70 dark:bg-zinc-900/60 rounded-lg p-2.5 space-y-1 font-mono text-[11px] border border-gray-100 dark:border-zinc-800">
                                                        {net.ipv4.address && (
                                                            <div className="flex justify-between">
                                                                <span className="text-gray-500 dark:text-zinc-400">{t('widgets.network.address', 'Address')}:</span>
                                                                <span className="text-gray-900 dark:text-zinc-100 font-semibold">{net.ipv4.address}</span>
                                                            </div>
                                                        )}
                                                        {net.ipv4.netmask && (
                                                            <div className="flex justify-between">
                                                                <span className="text-gray-500 dark:text-zinc-400">{t('widgets.network.netmask', 'Netmask')}:</span>
                                                                <span className="text-gray-700 dark:text-zinc-300">{net.ipv4.netmask}</span>
                                                            </div>
                                                        )}
                                                        {net.ipv4.gateway && (
                                                            <div className="flex justify-between">
                                                                <span className="text-gray-500 dark:text-zinc-400">{t('widgets.network.gateway', 'Gateway')}:</span>
                                                                <span className="text-gray-700 dark:text-zinc-300">{net.ipv4.gateway}</span>
                                                            </div>
                                                        )}
                                                        {net.ipv4.dns && net.ipv4.dns.length > 0 && (
                                                            <div className="flex justify-between">
                                                                <span className="text-gray-500 dark:text-zinc-400">{t('widgets.network.dns', 'DNS')}:</span>
                                                                <span className="text-gray-700 dark:text-zinc-300">{net.ipv4.dns.join(', ')}</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            )}

                                            {/* IPv6 Details */}
                                            {net.ipv6 && net.ipv6.address && (
                                                <div className="space-y-1.5 pt-1">
                                                    <span className="font-semibold text-gray-700 dark:text-zinc-300 text-[11px] uppercase tracking-wide">
                                                        {t('widgets.network.ipv6_address', 'IPv6 Address')}
                                                    </span>
                                                    <div className="bg-white/70 dark:bg-zinc-900/60 rounded-lg p-2.5 space-y-1 font-mono text-[11px] border border-gray-100 dark:border-zinc-800">
                                                        <div className="flex justify-between">
                                                            <span className="text-gray-500 dark:text-zinc-400">{t('widgets.network.address', 'Address')}:</span>
                                                            <span className="text-gray-900 dark:text-zinc-100 font-semibold truncate max-w-[200px]" title={net.ipv6.address}>
                                                                {net.ipv6.address}
                                                            </span>
                                                        </div>
                                                        {net.ipv6.netmask && (
                                                            <div className="flex justify-between">
                                                                <span className="text-gray-500 dark:text-zinc-400">{t('widgets.network.netmask', 'Netmask')}:</span>
                                                                <span className="text-gray-700 dark:text-zinc-300 truncate max-w-[200px]" title={net.ipv6.netmask}>
                                                                    {net.ipv6.netmask}
                                                                </span>
                                                            </div>
                                                        )}
                                                        {net.ipv6.gateway && (
                                                            <div className="flex justify-between">
                                                                <span className="text-gray-500 dark:text-zinc-400">{t('widgets.network.gateway', 'Gateway')}:</span>
                                                                <span className="text-gray-700 dark:text-zinc-300">{net.ipv6.gateway}</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })
                    )}
                </div>
            </div>

            {/* Footer Summary */}
            <div className="mt-4 pt-3 border-t border-gray-100 dark:border-zinc-800/80 text-xs text-gray-500 dark:text-zinc-400 flex justify-between items-center">
                <span>{t('widgets.network.total_interfaces', 'Total Interfaces')}</span>
                <div className="flex items-center gap-3">
                    <span className="font-semibold text-gray-900 dark:text-white font-mono">
                        {networks.length}
                    </span>
                    {onNavigateToNetwork && (
                        <button
                            type="button"
                            onClick={onNavigateToNetwork}
                            className="text-xs text-sky-600 dark:text-sky-400 hover:text-sky-700 dark:hover:text-sky-300 font-medium cursor-pointer transition-colors"
                        >
                            {t('nav.network', 'Network')} &rarr;
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
