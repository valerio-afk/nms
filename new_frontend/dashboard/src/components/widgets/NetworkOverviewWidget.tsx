import { Network, Wifi, Shield, ArrowUpDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { NetworkInterfaceItem } from '../../types/dashboard';

interface NetworkOverviewWidgetProps {
    networks: NetworkInterfaceItem[];
}

export default function NetworkOverviewWidget({ networks }: NetworkOverviewWidgetProps) {
    const { t } = useTranslation();

    const getIcon = (type: NetworkInterfaceItem['type']) => {
        switch (type) {
            case 'wifi':
                return <Wifi className="w-4 h-4 text-sky-500" />;
            case 'vpn':
                return <Shield className="w-4 h-4 text-emerald-500" />;
            default:
                return <Network className="w-4 h-4 text-indigo-500" />;
        }
    };

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 flex flex-col justify-between transition-all hover:shadow-md">
            <div>
                <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-sky-50 dark:bg-sky-950/40 text-sky-600 dark:text-sky-400">
                            <ArrowUpDown className="w-5 h-5" />
                        </div>
                        <div>
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                                {t('widgets.network.title', 'Network Interfaces')}
                            </h3>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {networks.filter(n => n.status === 'up').length} {t('widgets.network.up', 'Active')}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="mt-4 space-y-2.5 max-h-56 overflow-y-auto pr-1">
                    {networks.length === 0 ? (
                        <p className="text-xs text-gray-400 dark:text-zinc-500 py-4 text-center">
                            {t('widgets.network.no_interfaces', 'No interfaces detected')}
                        </p>
                    ) : (
                        networks.map((net, idx) => (
                            <div
                                key={net.name + idx}
                                className="flex items-center justify-between p-2.5 rounded-xl bg-gray-50 dark:bg-zinc-800/60 border border-gray-100 dark:border-zinc-800"
                            >
                                <div className="flex items-center gap-2.5 min-w-0">
                                    <div className="p-1 rounded bg-white dark:bg-zinc-700 shadow-xs">
                                        {getIcon(net.type)}
                                    </div>
                                    <div className="min-w-0">
                                        <p className="text-xs font-semibold text-gray-800 dark:text-zinc-200 truncate">
                                            {net.name}
                                        </p>
                                        <p className="text-[11px] font-mono text-gray-500 dark:text-zinc-400">
                                            {net.ipAddress || '—'}
                                        </p>
                                    </div>
                                </div>

                                <span
                                    className={`text-[11px] font-medium px-2 py-0.5 rounded-md ${
                                        net.status === 'up'
                                            ? 'bg-emerald-100/60 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400'
                                            : 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400'
                                    }`}
                                >
                                    {net.status === 'up' ? t('widgets.network.up', 'UP') : t('widgets.network.down', 'DOWN')}
                                </span>
                            </div>
                        ))
                    )}
                </div>
            </div>

            <div className="mt-4 pt-3 border-t border-gray-100 dark:border-zinc-800/80 text-xs text-gray-500 dark:text-zinc-400 flex justify-between">
                <span>{t('widgets.network.status', 'Total Interfaces')}</span>
                <span className="font-semibold text-gray-900 dark:text-white">
                    {networks.length}
                </span>
            </div>
        </div>
    );
}
