import { Disc, CheckCircle, AlertTriangle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { DiskItem } from '../../types/dashboard';
import { formatBytes } from '../../utils/formatters';

interface DiskOverviewWidgetProps {
    disks: DiskItem[];
}

export default function DiskOverviewWidget({ disks }: DiskOverviewWidgetProps) {
    const { t } = useTranslation();

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 flex flex-col justify-between transition-all hover:shadow-md">
            <div>
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

                <div className="mt-4 space-y-2.5 max-h-56 overflow-y-auto pr-1">
                    {disks.length === 0 ? (
                        <p className="text-xs text-gray-400 dark:text-zinc-500 py-4 text-center">
                            {t('widgets.disks.no_disks', 'No disks found or available')}
                        </p>
                    ) : (
                        disks.map((disk, idx) => {
                            const isHealthy = disk.status.toUpperCase() === 'ONLINE' || disk.status.toUpperCase() === 'OK';
                            return (
                                <div
                                    key={disk.name + idx}
                                    className="flex items-center justify-between p-2.5 rounded-xl bg-gray-50 dark:bg-zinc-800/60 border border-gray-100 dark:border-zinc-800"
                                >
                                    <div className="flex items-center gap-2.5 min-w-0">
                                        {isHealthy ? (
                                            <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0" />
                                        ) : (
                                            <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
                                        )}
                                        <div className="min-w-0">
                                            <p className="text-xs font-semibold text-gray-800 dark:text-zinc-200 truncate">
                                                {disk.name}
                                                {disk.model && (
                                                    <span className="ml-1 text-[11px] font-normal text-gray-500 dark:text-zinc-400">
                                                        ({disk.model})
                                                    </span>
                                                )}
                                            </p>
                                            <p className="text-[11px] text-gray-500 dark:text-zinc-400">
                                                {disk.size ? formatBytes(disk.size) : 'N/A'}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-2 text-right shrink-0">
                                        {typeof disk.temperature === 'number' && (
                                            <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-gray-200 dark:bg-zinc-700 text-gray-700 dark:text-zinc-300">
                                                {disk.temperature}°C
                                            </span>
                                        )}
                                        <span
                                            className={`text-[11px] font-medium px-2 py-0.5 rounded-md ${
                                                isHealthy
                                                    ? 'bg-emerald-100/60 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400'
                                                    : 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-400'
                                            }`}
                                        >
                                            {disk.status}
                                        </span>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </div>

            <div className="mt-4 pt-3 border-t border-gray-100 dark:border-zinc-800/80 text-xs text-gray-500 dark:text-zinc-400 flex justify-between">
                <span>{t('widgets.disks.disks_in_pool', 'Array Disks')}</span>
                <span className="font-semibold text-gray-900 dark:text-white">
                    {disks.filter(d => d.inPool).length} / {disks.length}
                </span>
            </div>
        </div>
    );
}
