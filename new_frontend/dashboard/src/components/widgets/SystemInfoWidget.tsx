import { Cpu, Clock, Server, CheckCircle2, ArrowDown, ArrowUp, HardDrive, Layers, Activity } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { SystemInfo } from '../../types/dashboard';
import { formatUptime, formatBootDate, formatBytes } from '../../utils/formatters';

interface SystemInfoWidgetProps {
    system: SystemInfo;
}

export default function SystemInfoWidget({ system }: SystemInfoWidgetProps) {
    const { t, i18n } = useTranslation();

    // RAM usage percentage: prefer backend's memoryLoad, fallback to memoryUsed / memoryTotal
    const memPercent = typeof system.memoryLoad === 'number'
        ? system.memoryLoad
        : system.memoryTotal && system.memoryUsed
            ? Math.round((system.memoryUsed / system.memoryTotal) * 100)
            : null;

    const swapPercent = typeof system.swapLoad === 'number' ? system.swapLoad : null;
    const cpuPercent = typeof system.cpuLoad === 'number' ? system.cpuLoad : null;

    const bootDateStr = formatBootDate(system.uptime, i18n.language);
    const uptimeDuration = formatUptime(system.uptime);

    const netRecv = system.netCounters?.bytes_recv;
    const netSent = system.netCounters?.bytes_sent;

    const getProgressColor = (pct: number) => {
        if (pct >= 90) return 'bg-red-500';
        if (pct >= 75) return 'bg-amber-500';
        return 'bg-emerald-500';
    };

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 flex flex-col justify-between transition-all hover:shadow-md">
            <div>
                {/* Header */}
                <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-teal-50 dark:bg-teal-950/40 text-teal-600 dark:text-teal-400">
                            <Server className="w-5 h-5" />
                        </div>
                        <div>
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                                {t('widgets.system.title', 'System Information')}
                            </h3>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {system.nmsVer ? `v${system.nmsVer}` : (system.hostname || 'NMS Node')}
                            </p>
                        </div>
                    </div>

                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {t('widgets.system.up_to_date', 'Online')}
                    </span>
                </div>

                {/* System Specs List */}
                <div className="mt-4 space-y-2.5 text-xs">
                    {/* OS */}
                    <div className="flex justify-between items-center">
                        <span className="text-gray-500 dark:text-zinc-400">{t('widgets.system.os', 'OS')}</span>
                        <span className="font-medium text-gray-900 dark:text-zinc-200 truncate max-w-[200px]" title={system.os}>
                            {system.os || 'Linux'}
                        </span>
                    </div>

                    {/* CPU Model */}
                    {system.cpu && (
                        <div className="flex justify-between items-center">
                            <span className="text-gray-500 dark:text-zinc-400">{t('widgets.system.cpu', 'CPU')}</span>
                            <span className="font-medium text-gray-900 dark:text-zinc-200 truncate max-w-[200px]" title={system.cpu}>
                                {system.cpu}
                            </span>
                        </div>
                    )}

                    {/* NMS Version */}
                    {system.nmsVer && (
                        <div className="flex justify-between items-center">
                            <span className="text-gray-500 dark:text-zinc-400">{t('widgets.system.nms_version', 'NMS Version')}</span>
                            <span className="font-mono font-medium text-gray-900 dark:text-zinc-200">
                                {system.nmsVer}
                            </span>
                        </div>
                    )}

                    {/* Uptime */}
                    <div className="flex justify-between items-start">
                        <span className="text-gray-500 dark:text-zinc-400 flex items-center gap-1">
                            <Clock className="w-3.5 h-3.5" />
                            {t('widgets.system.uptime', 'Uptime')}
                        </span>
                        <div className="text-right">
                            <span className="font-mono font-medium text-gray-900 dark:text-zinc-200">
                                {uptimeDuration}
                            </span>
                            {bootDateStr && (
                                <p className="text-[10px] text-gray-400 dark:text-zinc-500 truncate max-w-[190px]">
                                    {t('widgets.system.since', 'Since')} {bootDateStr}
                                </p>
                            )}
                        </div>
                    </div>

                    {/* Divider */}
                    <div className="pt-2 border-t border-gray-100 dark:border-zinc-800/60" />

                    {/* CPU Load Progress */}
                    {cpuPercent !== null && (
                        <div>
                            <div className="flex justify-between text-xs mb-1">
                                <span className="text-gray-600 dark:text-zinc-300 flex items-center gap-1 font-medium">
                                    <Cpu className="w-3.5 h-3.5 text-indigo-500" />
                                    {t('widgets.system.cpu_load', 'CPU Load')}
                                </span>
                                <span className="font-semibold text-gray-800 dark:text-gray-200 font-mono">
                                    {cpuPercent}%
                                </span>
                            </div>
                            <div className="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all duration-500 ${getProgressColor(cpuPercent)}`}
                                    style={{ width: `${Math.min(100, cpuPercent)}%` }}
                                />
                            </div>
                        </div>
                    )}

                    {/* RAM Usage Progress */}
                    {memPercent !== null && (
                        <div>
                            <div className="flex justify-between text-xs mb-1">
                                <span className="text-gray-600 dark:text-zinc-300 flex items-center gap-1 font-medium">
                                    <Layers className="w-3.5 h-3.5 text-sky-500" />
                                    {t('widgets.system.ram_usage', 'RAM Usage')}
                                </span>
                                <span className="font-semibold text-gray-800 dark:text-gray-200 font-mono">
                                    {system.memoryTotal && system.memoryUsed
                                        ? `${formatBytes(system.memoryUsed)} / ${formatBytes(system.memoryTotal)} (${memPercent}%)`
                                        : `${memPercent}%`}
                                </span>
                            </div>
                            <div className="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all duration-500 ${getProgressColor(memPercent)}`}
                                    style={{ width: `${Math.min(100, memPercent)}%` }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Swap Usage Progress */}
                    {swapPercent !== null && (
                        <div>
                            <div className="flex justify-between text-xs mb-1">
                                <span className="text-gray-600 dark:text-zinc-300 flex items-center gap-1 font-medium">
                                    <HardDrive className="w-3.5 h-3.5 text-amber-500" />
                                    {t('widgets.system.swap_usage', 'Swap Usage')}
                                </span>
                                <span className="font-semibold text-gray-800 dark:text-gray-200 font-mono">
                                    {swapPercent}%
                                </span>
                            </div>
                            <div className="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all duration-500 ${getProgressColor(swapPercent)}`}
                                    style={{ width: `${Math.min(100, swapPercent)}%` }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Network Throughput */}
                    {system.netCounters && (
                        <div className="pt-2">
                            <div className="flex justify-between items-center mb-1">
                                <span className="text-gray-600 dark:text-zinc-300 flex items-center gap-1 font-medium">
                                    <Activity className="w-3.5 h-3.5 text-teal-500" />
                                    {t('widgets.system.network_speed', 'Network Throughput')}
                                </span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 p-2 rounded-xl bg-gray-50 dark:bg-zinc-800/50 border border-gray-100 dark:border-zinc-800">
                                <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                                    <ArrowDown className="w-3.5 h-3.5 shrink-0" />
                                    <div className="truncate">
                                        <p className="text-[10px] text-gray-400 dark:text-zinc-500 leading-none">{t('widgets.system.download', 'Download')}</p>
                                        <p className="font-mono font-semibold text-xs mt-0.5">{formatBytes(netRecv || 0)}/s</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-1.5 text-sky-600 dark:text-sky-400">
                                    <ArrowUp className="w-3.5 h-3.5 shrink-0" />
                                    <div className="truncate">
                                        <p className="text-[10px] text-gray-400 dark:text-zinc-500 leading-none">{t('widgets.system.upload', 'Upload')}</p>
                                        <p className="font-mono font-semibold text-xs mt-0.5">{formatBytes(netSent || 0)}/s</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
