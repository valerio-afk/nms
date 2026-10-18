import { HardDrive, CheckCircle2, AlertCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { PoolStatus } from '../../types/dashboard';
import { formatBytes, formatPercent } from '../../utils/formatters';

interface DiskUsageWidgetProps {
    pool: PoolStatus;
    userQuota?: { used: number; quota: number } | null;
}

export default function DiskUsageWidget({ pool, userQuota }: DiskUsageWidgetProps) {
    const { t } = useTranslation();

    const used = pool.capacity?.used || 0;
    const total = pool.capacity?.total || 0;
    const percent = formatPercent(used, total);

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 flex flex-col justify-between transition-all hover:shadow-md">
            <div>
                <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400">
                            <HardDrive className="w-5 h-5" />
                        </div>
                        <div>
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                                {t('widgets.storage.title', 'Storage Array')}
                            </h3>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {pool.isMounted ? t('widgets.storage.mounted', 'Mounted & Online') : t('widgets.storage.unmounted', 'Unmounted')}
                            </p>
                        </div>
                    </div>

                    <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                            pool.isMounted
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
                                : pool.isConfigured
                                ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400'
                                : 'bg-gray-100 text-gray-600 dark:bg-zinc-800 dark:text-gray-400'
                        }`}
                    >
                        {pool.isMounted ? (
                            <>
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                {t('widgets.storage.health', 'Healthy')}
                            </>
                        ) : (
                            <>
                                <AlertCircle className="w-3.5 h-3.5" />
                                {pool.isConfigured ? t('widgets.storage.unmounted', 'Unmounted') : t('widgets.storage.not_configured', 'Not Setup')}
                            </>
                        )}
                    </span>
                </div>

                <div className="mt-5 space-y-4">
                    <div>
                        <div className="flex justify-between text-sm mb-1.5">
                            <span className="font-medium text-gray-700 dark:text-gray-300">
                                {formatBytes(used)} <span className="text-xs text-gray-400 font-normal">/ {formatBytes(total)}</span>
                            </span>
                            <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                                {percent}%
                            </span>
                        </div>
                        <div className="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-3 overflow-hidden p-0.5">
                            <div
                                className={`h-full rounded-full transition-all duration-500 ${
                                    percent > 90
                                        ? 'bg-red-500'
                                        : percent > 75
                                        ? 'bg-amber-500'
                                        : 'bg-gradient-to-r from-indigo-500 to-purple-600'
                                }`}
                                style={{ width: `${percent}%` }}
                            />
                        </div>
                    </div>

                    {userQuota && userQuota.quota > 0 && (
                        <div className="pt-3 border-t border-gray-100 dark:border-zinc-800/80">
                            <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                                <span>{t('widgets.storage.quota', 'Your User Quota')}</span>
                                <span className="font-medium text-gray-800 dark:text-gray-200">
                                    {formatBytes(userQuota.used)} / {formatBytes(userQuota.quota)}
                                </span>
                            </div>
                            <div className="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                                <div
                                    className="h-full bg-indigo-500 rounded-full"
                                    style={{ width: `${formatPercent(userQuota.used, userQuota.quota)}%` }}
                                />
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <div className="mt-5 pt-3 border-t border-gray-100 dark:border-zinc-800/80 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                <span>{t('widgets.storage.free', 'Free Space')}</span>
                <span className="font-semibold text-gray-900 dark:text-white">
                    {formatBytes(Math.max(0, total - used))}
                </span>
            </div>
        </div>
    );
}
