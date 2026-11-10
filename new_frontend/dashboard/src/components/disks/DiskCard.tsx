import { HardDrive, Activity, RefreshCw, Thermometer, ShieldCheck, ShieldAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { DiskItem } from '../../types/dashboard';
import { formatBytes } from '../../utils/formatters';

interface DiskCardProps {
    disk: DiskItem;
    index: number;
    onCheckHealth?: (disk: DiskItem) => void;
    onReplace?: (disk: DiskItem) => void;
    onFormat?: (disk: DiskItem) => void;
}

export default function DiskCard({
    disk,
    index,
    onCheckHealth,
    onReplace,
    onFormat
}: DiskCardProps) {
    const { t } = useTranslation();

    const getStatusCharm = (statusCode: number) => {
        switch (statusCode) {
            case 1:
                return '🟢';
            case 0:
                return '🟡';
            case -1:
                return '🔴';
            case -2:
                return '⚠️';
            default:
                return '❓';
        }
    };

    const getStatusBadge = (statusCode: number, statusStr: string) => {
        switch (statusCode) {
            case 1:
                return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/50">
                        <ShieldCheck className="w-3 h-3" />
                        {t('disks.status.online', 'Online')}
                    </span>
                );
            case 0:
                return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400 border border-blue-200 dark:border-blue-800/50">
                        {t('disks.status.new', 'New / Unassigned')}
                    </span>
                );
            case -1:
                return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 dark:bg-zinc-800 dark:text-gray-300 border border-gray-300 dark:border-zinc-700">
                        {t('disks.status.offline', 'Offline')}
                    </span>
                );
            case -2:
                return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400 border border-red-200 dark:border-red-800/50">
                        <ShieldAlert className="w-3 h-3" />
                        {t('disks.status.corrupted', 'Corrupted')}
                    </span>
                );
            default:
                return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                        {statusStr}
                    </span>
                );
        }
    };

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-5 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 flex flex-col justify-between transition-all hover:shadow-md">
            <div>
                {/* Header: Disk Title + Charm + Status Badge */}
                <div className="flex items-center justify-between pb-3 border-b border-gray-100 dark:border-zinc-800">
                    <div className="flex items-center gap-2.5">
                        <div className="p-2 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400">
                            <HardDrive className="w-4 h-4" />
                        </div>
                        <div>
                            <div className="flex items-center gap-1.5">
                                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                                    {t('disks.disk_index', 'Disk {{index}}', { index: index + 1 })}
                                </h3>
                                <span className="text-sm" title={disk.status}>
                                    {getStatusCharm(disk.statusCode)}
                                </span>
                            </div>
                            <span className="text-[11px] font-mono text-gray-400 dark:text-zinc-500">
                                {disk.path || disk.name}
                            </span>
                        </div>
                    </div>
                    {getStatusBadge(disk.statusCode, disk.status)}
                </div>

                {/* Body Specs */}
                <div className="mt-4 space-y-2.5 text-xs">
                    <div>
                        <p className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-zinc-500 font-medium">
                            {t('disks.model', 'Model')}
                        </p>
                        <p className="font-medium text-gray-900 dark:text-zinc-100 truncate mt-0.5" title={disk.model}>
                            {disk.model || t('disks.unknown_model', 'Unknown Device')}
                        </p>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-1">
                        <div>
                            <p className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-zinc-500 font-medium">
                                {t('disks.serial', 'Serial')}
                            </p>
                            <p className="font-mono text-gray-700 dark:text-zinc-300 truncate mt-0.5">
                                {disk.serial || '-'}
                            </p>
                        </div>
                        <div>
                            <p className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-zinc-500 font-medium">
                                {t('disks.capacity', 'Size')}
                            </p>
                            <p className="font-semibold text-gray-900 dark:text-white mt-0.5">
                                {disk.size ? formatBytes(disk.size) : '-'}
                            </p>
                        </div>
                    </div>

                    {/* Temperature indicator if available */}
                    {typeof disk.temperature === 'number' && (
                        <div className="flex items-center gap-1 text-[11px] text-gray-500 dark:text-zinc-400 pt-1">
                            <Thermometer className="w-3.5 h-3.5 text-amber-500" />
                            <span>{t('disks.temperature', 'Temperature')}:</span>
                            <span className="font-semibold text-gray-800 dark:text-zinc-200">
                                {disk.temperature}°C
                            </span>
                        </div>
                    )}
                </div>
            </div>

            {/* Actions */}
            <div className="mt-5 pt-3 border-t border-gray-100 dark:border-zinc-800/80 flex flex-col gap-2">
                {disk.statusCode === -2 && onReplace && (
                    <button
                        type="button"
                        onClick={() => onReplace(disk)}
                        className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl bg-amber-500 text-white hover:bg-amber-600 transition-colors shadow-xs cursor-pointer"
                    >
                        <RefreshCw className="w-3.5 h-3.5" />
                        {t('disks.replace', 'Replace')}
                    </button>
                )}

                {onCheckHealth && (
                    <button
                        type="button"
                        onClick={() => onCheckHealth(disk)}
                        className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 transition-colors cursor-pointer"
                    >
                        <Activity className="w-3.5 h-3.5" />
                        {t('disks.check_health', 'Check disk health')}
                    </button>
                )}

                {disk.statusCode === 0 && onFormat && (
                    <button
                        type="button"
                        onClick={() => onFormat(disk)}
                        className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-xl text-gray-600 dark:text-zinc-400 hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                    >
                        {t('disks.format', 'Format')}
                    </button>
                )}
            </div>
        </div>
    );
}
