import { Cpu, Clock, Server, CheckCircle2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { SystemInfo } from '../../types/dashboard';
import { formatUptime, formatBytes } from '../../utils/formatters';

interface SystemInfoWidgetProps {
    system: SystemInfo;
}

export default function SystemInfoWidget({ system }: SystemInfoWidgetProps) {
    const { t } = useTranslation();

    const memPercent = system.memoryTotal && system.memoryUsed
        ? Math.round((system.memoryUsed / system.memoryTotal) * 100)
        : null;

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 flex flex-col justify-between transition-all hover:shadow-md">
            <div>
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
                                {system.hostname || 'NMS Node'}
                            </p>
                        </div>
                    </div>

                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {t('widgets.system.up_to_date', 'Online')}
                    </span>
                </div>

                <div className="mt-4 space-y-3">
                    <div className="flex justify-between items-center text-xs">
                        <span className="text-gray-500 dark:text-gray-400">{t('widgets.system.os', 'OS / Kernel')}</span>
                        <span className="font-medium text-gray-900 dark:text-gray-200 truncate max-w-[180px]">
                            {system.os || 'Linux'} {system.kernel ? `(${system.kernel})` : ''}
                        </span>
                    </div>

                    <div className="flex justify-between items-center text-xs">
                        <span className="text-gray-500 dark:text-gray-400 flex items-center gap-1">
                            <Clock className="w-3.5 h-3.5" />
                            {t('widgets.system.uptime', 'Uptime')}
                        </span>
                        <span className="font-mono font-medium text-gray-900 dark:text-gray-200">
                            {formatUptime(system.uptime)}
                        </span>
                    </div>

                    {typeof system.cpuLoad === 'number' && (
                        <div>
                            <div className="flex justify-between text-xs mb-1">
                                <span className="text-gray-500 dark:text-gray-400 flex items-center gap-1">
                                    <Cpu className="w-3.5 h-3.5" />
                                    {t('widgets.system.cpu', 'CPU Load')}
                                </span>
                                <span className="font-semibold text-gray-800 dark:text-gray-200">
                                    {system.cpuLoad}%
                                </span>
                            </div>
                            <div className="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all ${
                                        system.cpuLoad > 85 ? 'bg-red-500' : 'bg-teal-500'
                                    }`}
                                    style={{ width: `${Math.min(100, system.cpuLoad)}%` }}
                                />
                            </div>
                        </div>
                    )}

                    {memPercent !== null && (
                        <div>
                            <div className="flex justify-between text-xs mb-1">
                                <span className="text-gray-500 dark:text-gray-400">
                                    {t('widgets.system.memory', 'Memory')}
                                </span>
                                <span className="font-medium text-gray-800 dark:text-gray-200">
                                    {formatBytes(system.memoryUsed || 0)} / {formatBytes(system.memoryTotal || 0)} ({memPercent}%)
                                </span>
                            </div>
                            <div className="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all ${
                                        memPercent > 90 ? 'bg-red-500' : 'bg-indigo-500'
                                    }`}
                                    style={{ width: `${memPercent}%` }}
                                />
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <div className="mt-4 pt-3 border-t border-gray-100 dark:border-zinc-800/80 text-xs text-gray-500 dark:text-zinc-400 flex justify-between">
                <span>{t('widgets.system.hostname', 'Host Node')}</span>
                <span className="font-mono font-medium text-gray-900 dark:text-white">
                    {system.hostname || 'nms-server'}
                </span>
            </div>
        </div>
    );
}
