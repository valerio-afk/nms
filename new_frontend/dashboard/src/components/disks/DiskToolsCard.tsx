import { Wrench, Search, Database, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { ScrubInfo } from '../../types/dashboard';

interface DiskToolsCardProps {
    isMounted: boolean;
    scrubInfo?: ScrubInfo | null;
    onVerify: () => void;
    onToggleMount: () => void;
    actionLoading?: string | null;
}

export default function DiskToolsCard({
    isMounted,
    scrubInfo,
    onVerify,
    onToggleMount,
    actionLoading = null
}: DiskToolsCardProps) {
    const { t, i18n } = useTranslation();

    const isScrubbing = scrubInfo?.ongoing || actionLoading === 'verify';

    const formatLastScrub = (epoch?: number | null) => {
        if (!epoch) return t('disks.tools.never', 'Never');
        try {
            return new Date(epoch * 1000).toLocaleDateString(i18n.language === 'it' ? 'it-IT' : 'en-US', {
                weekday: 'short',
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return new Date(epoch * 1000).toLocaleString();
        }
    };

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 transition-all hover:shadow-md">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400">
                        <Wrench className="w-5 h-5" />
                    </div>
                    <div>
                        <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                            {t('disks.tools.title', 'Disk Tools')}
                        </h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                            {t('disks.tools.subtitle', 'Array maintenance and operations')}
                        </p>
                    </div>
                </div>
            </div>

            {/* Quick Action Tiles */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-5">
                {/* 1. Verify */}
                <button
                    type="button"
                    onClick={onVerify}
                    disabled={isScrubbing}
                    className="flex flex-col items-start p-4 rounded-xl bg-gray-50 dark:bg-zinc-800/60 border border-gray-200/80 dark:border-zinc-700/80 hover:bg-indigo-50/50 dark:hover:bg-zinc-800 hover:border-indigo-300 dark:hover:border-zinc-600 transition-all text-left cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed group"
                >
                    <div className="flex items-center justify-between w-full mb-2">
                        <div className="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 group-hover:scale-105 transition-transform">
                            {isScrubbing ? (
                                <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
                            ) : (
                                <Search className="w-4 h-4" />
                            )}
                        </div>
                        <span className="text-[11px] font-medium text-indigo-600 dark:text-indigo-400">
                            {t('disks.tools.verify_action', 'Run')}
                        </span>
                    </div>
                    <span className="text-sm font-semibold text-gray-900 dark:text-white">
                        {t('disks.tools.verify', 'Verify')}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-zinc-400 mt-1">
                        {isScrubbing
                            ? t('disks.tools.verify_in_progress', 'Verification in progress...')
                            : `${t('disks.tools.last_verified', 'Last verified')}: ${formatLastScrub(scrubInfo?.last)}`}
                    </span>
                </button>

                {/* 2. Mount / Unmount */}
                <button
                    type="button"
                    onClick={onToggleMount}
                    disabled={actionLoading === 'mount'}
                    className="flex flex-col items-start p-4 rounded-xl bg-gray-50 dark:bg-zinc-800/60 border border-gray-200/80 dark:border-zinc-700/80 hover:bg-sky-50/50 dark:hover:bg-zinc-800 hover:border-sky-300 dark:hover:border-zinc-600 transition-all text-left cursor-pointer disabled:opacity-60 group"
                >
                    <div className="flex items-center justify-between w-full mb-2">
                        <div
                            className={`p-2 rounded-lg ${
                                isMounted
                                    ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400'
                                    : 'bg-amber-100 dark:bg-amber-950 text-amber-600 dark:text-amber-400'
                            } group-hover:scale-105 transition-transform`}
                        >
                            {actionLoading === 'mount' ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                                <Database className="w-4 h-4" />
                            )}
                        </div>
                        <span
                            className={`text-[11px] font-medium ${
                                isMounted ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'
                            }`}
                        >
                            {isMounted ? t('disks.tools.unmount', 'Unmount') : t('disks.tools.mount', 'Mount')}
                        </span>
                    </div>
                    <span className="text-sm font-semibold text-gray-900 dark:text-white">
                        {isMounted ? t('disks.tools.unmount', 'Unmount Array') : t('disks.tools.mount', 'Mount Array')}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-zinc-400 mt-1">
                        {isMounted
                            ? t('disks.tools.mounted_desc', 'Disk array is mounted and accessible')
                            : t('disks.tools.unmounted_desc', 'Disk array is unmounted')}
                    </span>
                </button>
            </div>
        </div>
    );
}
