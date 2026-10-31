import { Disc, AlertTriangle, Shield, Check, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { DiskItem, PoolStatus } from '../../types/dashboard';
import { formatBytes } from '../../utils/formatters';

interface DiskOverviewWidgetProps {
    disks: DiskItem[];
    pool?: PoolStatus | null;
    onNavigateToDisks?: () => void;
}

export default function DiskOverviewWidget({ disks, pool, onNavigateToDisks }: DiskOverviewWidgetProps) {
    const { t } = useTranslation();

    const getStatusInfo = (disk: DiskItem) => {
        const code = disk.statusCode;
        switch (code) {
            case 1:
                return {
                    label: t('widgets.disks.online', 'Online'),
                    charm: '🟢',
                    className: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-400 dark:border-emerald-800/40'
                };
            case 0:
                return {
                    label: t('widgets.disks.new', 'New'),
                    charm: '✴️',
                    className: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/50 dark:text-blue-400 dark:border-blue-800/40'
                };
            case -1:
                return {
                    label: t('widgets.disks.offline', 'Offline'),
                    charm: '🔴',
                    className: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/50 dark:text-red-400 dark:border-red-800/40'
                };
            case -2:
                return {
                    label: t('widgets.disks.corrupted', 'Corrupted'),
                    charm: '⚠️',
                    className: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/50 dark:text-amber-400 dark:border-amber-800/40'
                };
            default:
                return {
                    label: disk.status || t('widgets.disks.unknown', 'Unknown'),
                    charm: '❓',
                    className: 'bg-zinc-100 text-zinc-700 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-700'
                };
        }
    };

    const poolSettings = pool?.settings;

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 flex flex-col justify-between transition-all hover:shadow-md">
            <div>
                {/* Header */}
                <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400">
                            <Disc className="w-5 h-5" />
                        </div>
                        <div>
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                                {t('widgets.disks.title', 'Disks Overview')}
                            </h3>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {disks.length} {t('widgets.disks.sys_disks', 'Disks Detected')}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Disks Table or Empty State */}
                {disks.length === 0 ? (
                    <div className="p-4 my-4 rounded-xl border border-amber-200 bg-amber-50/80 dark:bg-amber-950/30 dark:border-amber-800/50 text-amber-700 dark:text-amber-400 text-xs flex items-center gap-2.5">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span className="font-medium">{t('widgets.disks.no_disks', 'No hard drive inserted!')}</span>
                    </div>
                ) : (
                    <div className="mt-4 overflow-x-auto">
                        <table className="w-full text-left text-xs">
                            <thead>
                                <tr className="border-b border-gray-100 dark:border-zinc-800 text-gray-400 dark:text-zinc-500 uppercase tracking-wider text-[10px]">
                                    <th className="pb-2 font-medium">{t('widgets.disks.name', 'Name')}</th>
                                    <th className="pb-2 font-medium">{t('widgets.disks.model', 'Model')}</th>
                                    <th className="pb-2 font-medium text-right">{t('widgets.disks.size', 'Size')}</th>
                                    <th className="pb-2 font-medium text-right">{t('widgets.disks.status', 'Status')}</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50 dark:divide-zinc-800/60">
                                {disks.map((disk, idx) => {
                                    const statusInfo = getStatusInfo(disk);
                                    return (
                                        <tr key={disk.name + idx} className="hover:bg-gray-50/60 dark:hover:bg-zinc-800/40 transition-colors">
                                            <td className="py-2.5 pr-2 font-mono font-semibold text-gray-900 dark:text-white" title={disk.path || `/dev/${disk.name}`}>
                                                {disk.name}
                                            </td>
                                            <td className="py-2.5 px-2 text-gray-600 dark:text-zinc-300 max-w-[130px] truncate" title={disk.model || disk.serial || ''}>
                                                {disk.model || '-'}
                                            </td>
                                            <td className="py-2.5 px-2 text-right font-medium text-gray-700 dark:text-zinc-300 whitespace-nowrap">
                                                {typeof disk.size === 'number' && disk.size > 0 ? formatBytes(disk.size) : '-'}
                                            </td>
                                            <td className="py-2.5 pl-2 text-right whitespace-nowrap">
                                                <span
                                                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-medium border ${statusInfo.className}`}
                                                    title={`${statusInfo.charm} ${statusInfo.label}`}
                                                >
                                                    <span className="text-[10px] leading-none">{statusInfo.charm}</span>
                                                    <span>{statusInfo.label}</span>
                                                </span>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}

                {/* Pool Options / Configuration Info */}
                {pool && (
                    <div className="mt-4 pt-3 border-t border-gray-100 dark:border-zinc-800">
                        {pool.isConfigured && poolSettings ? (
                            <div className="grid grid-cols-3 gap-2 text-center text-xs">
                                <div className="p-2 rounded-xl bg-gray-50 dark:bg-zinc-800/60 border border-gray-100 dark:border-zinc-800 flex flex-col items-center">
                                    <span className="text-[10px] text-gray-500 dark:text-zinc-400 font-medium">{t('widgets.disks.encryption', 'Encryption')}</span>
                                    <span className={`inline-flex items-center gap-1 text-[11px] font-semibold mt-1 ${poolSettings.encryption ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-400 dark:text-zinc-500'}`}>
                                        {poolSettings.encryption ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
                                        {poolSettings.encryption ? t('widgets.disks.enabled', 'Enabled') : t('widgets.disks.disabled', 'Disabled')}
                                    </span>
                                </div>
                                <div className="p-2 rounded-xl bg-gray-50 dark:bg-zinc-800/60 border border-gray-100 dark:border-zinc-800 flex flex-col items-center">
                                    <span className="text-[10px] text-gray-500 dark:text-zinc-400 font-medium">{t('widgets.disks.redundancy', 'Redundancy')}</span>
                                    <span className={`inline-flex items-center gap-1 text-[11px] font-semibold mt-1 ${poolSettings.redundancy ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-500 dark:text-amber-400'}`}>
                                        {poolSettings.redundancy ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
                                        {poolSettings.redundancy ? t('widgets.disks.enabled', 'Enabled') : t('widgets.disks.disabled', 'Disabled')}
                                    </span>
                                </div>
                                <div className="p-2 rounded-xl bg-gray-50 dark:bg-zinc-800/60 border border-gray-100 dark:border-zinc-800 flex flex-col items-center">
                                    <span className="text-[10px] text-gray-500 dark:text-zinc-400 font-medium">{t('widgets.disks.compression', 'Compression')}</span>
                                    <span className={`inline-flex items-center gap-1 text-[11px] font-semibold mt-1 ${poolSettings.compression ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-400 dark:text-zinc-500'}`}>
                                        {poolSettings.compression ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
                                        {poolSettings.compression ? t('widgets.disks.enabled', 'Enabled') : t('widgets.disks.disabled', 'Disabled')}
                                    </span>
                                </div>
                            </div>
                        ) : !pool.isConfigured ? (
                            <div className="p-3 rounded-xl border border-amber-200 bg-amber-50/70 dark:bg-amber-950/30 dark:border-amber-800/50 text-amber-700 dark:text-amber-400 text-xs flex items-start gap-2.5">
                                <Shield className="w-4 h-4 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
                                <div>
                                    <p className="font-medium">{t('widgets.disks.no_pool_config', 'No disk array configuration found.')}</p>
                                    <p className="mt-0.5 text-[11px] text-amber-600 dark:text-amber-400">
                                        {onNavigateToDisks ? (
                                            <button
                                                type="button"
                                                onClick={onNavigateToDisks}
                                                className="underline hover:text-amber-800 dark:hover:text-amber-300 font-semibold cursor-pointer"
                                            >
                                                {t('widgets.disks.go_to_disk_mngt', 'Go to Disk Management to configure your disk array.')}
                                            </button>
                                        ) : (
                                            t('widgets.disks.go_to_disk_mngt', 'Go to Disk Management to configure your disk array.')
                                        )}
                                    </p>
                                </div>
                            </div>
                        ) : null}
                    </div>
                )}
            </div>

            {/* Footer Summary */}
            <div className="mt-4 pt-3 border-t border-gray-100 dark:border-zinc-800/80 text-xs text-gray-500 dark:text-zinc-400 flex justify-between items-center">
                <span>{t('widgets.disks.disks_in_pool', 'Disks in Array')}</span>
                <span className="font-semibold text-gray-900 dark:text-white font-mono">
                    {disks.filter(d => d.inPool).length} / {disks.length}
                </span>
            </div>
        </div>
    );
}
