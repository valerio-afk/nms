import { useState, useEffect } from 'react';
import { X, Activity, Thermometer, Clock, ShieldCheck, ShieldAlert, Play, CheckCircle2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { DiskItem, SmartInfo } from '../../types/dashboard';
import { fetchSmartInfo, runSmartTest } from '../../utils/api';

interface SmartModalProps {
    disk: DiskItem | null;
    isOpen: boolean;
    onClose: () => void;
}

export default function SmartModal({ disk, isOpen, onClose }: SmartModalProps) {
    const { t } = useTranslation();

    const [smartData, setSmartData] = useState<SmartInfo | null>(null);
    const [loading, setLoading] = useState(false);
    const [testLoading, setTestLoading] = useState<'short' | 'long' | null>(null);
    const [testMessage, setTestMessage] = useState<string | null>(null);

    const devPath = disk?.path || (disk?.name ? `/dev/${disk.name}` : '');

    useEffect(() => {
        if (!isOpen || !devPath) {
            setSmartData(null);
            setTestMessage(null);
            return;
        }

        let isMounted = true;
        setLoading(true);
        fetchSmartInfo(devPath)
            .then(data => {
                if (isMounted) setSmartData(data);
            })
            .catch(err => {
                console.error('Failed to load SMART info', err);
            })
            .finally(() => {
                if (isMounted) setLoading(false);
            });

        return () => {
            isMounted = false;
        };
    }, [isOpen, devPath]);

    const handleRunTest = async (testType: 'short' | 'long') => {
        if (!devPath) return;
        setTestLoading(testType);
        setTestMessage(null);
        try {
            await runSmartTest(devPath, testType);
            setTestMessage(
                testType === 'short'
                    ? t('disks.smart.test_short_started', 'Quick self-test initiated successfully.')
                    : t('disks.smart.test_long_started', 'Extended self-test initiated successfully.')
            );
            // Refresh smart info after brief pause
            setTimeout(() => {
                fetchSmartInfo(devPath).then(data => setSmartData(data));
            }, 1000);
        } catch (err: any) {
            setTestMessage(err?.message || t('disks.smart.test_failed', 'Failed to start self-test.'));
        } finally {
            setTestLoading(null);
        }
    };

    if (!isOpen || !disk) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
            <div className="bg-white dark:bg-zinc-900 rounded-2xl w-full max-w-3xl max-h-[90vh] shadow-2xl ring-1 ring-gray-900/10 dark:ring-white/10 flex flex-col overflow-hidden">
                {/* Modal Header */}
                <div className="flex items-center justify-between p-5 border-b border-gray-100 dark:border-zinc-800">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400">
                            <Activity className="w-5 h-5" />
                        </div>
                        <div>
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                                {t('disks.smart.modal_title', 'Disk Diagnostic')}
                            </h3>
                            <p className="text-xs text-gray-500 dark:text-zinc-400 font-mono">
                                {disk.model} ({devPath})
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-zinc-200 hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto space-y-6 text-xs">
                    {loading ? (
                        <div className="py-12 text-center text-gray-400 dark:text-zinc-500">
                            <Activity className="w-8 h-8 animate-pulse mx-auto mb-2 text-indigo-500" />
                            <p>{t('disks.smart.loading', 'Checking disk health...')}</p>
                        </div>
                    ) : (
                        <>
                            {testMessage && (
                                <div className="p-3.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900/50 text-indigo-700 dark:text-indigo-300">
                                    {testMessage}
                                </div>
                            )}

                            {/* Status Overview Cards */}
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                {/* Passed Status */}
                                <div className="p-3.5 rounded-xl bg-gray-50 dark:bg-zinc-800/50 border border-gray-100 dark:border-zinc-800">
                                    <span className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-zinc-500 font-semibold">
                                        {t('disks.smart.overall_health', 'Health Assessment')}
                                    </span>
                                    <div className="flex items-center gap-1.5 mt-1">
                                        {smartData?.passed ? (
                                            <>
                                                <ShieldCheck className="w-4 h-4 text-emerald-500" />
                                                <span className="font-semibold text-emerald-600 dark:text-emerald-400 text-sm">
                                                    {t('disks.smart.passed', 'Passed')}
                                                </span>
                                            </>
                                        ) : (
                                            <>
                                                <ShieldAlert className="w-4 h-4 text-red-500" />
                                                <span className="font-semibold text-red-600 dark:text-red-400 text-sm">
                                                    {t('disks.smart.warning', 'Check')}
                                                </span>
                                            </>
                                        )}
                                    </div>
                                </div>

                                {/* Temperature */}
                                <div className="p-3.5 rounded-xl bg-gray-50 dark:bg-zinc-800/50 border border-gray-100 dark:border-zinc-800">
                                    <span className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-zinc-500 font-semibold">
                                        {t('disks.smart.temperature', 'Temperature')}
                                    </span>
                                    <div className="flex items-center gap-1.5 mt-1">
                                        <Thermometer className="w-4 h-4 text-amber-500" />
                                        <span className="font-semibold text-gray-900 dark:text-white text-sm">
                                            {smartData?.temperature ? `${smartData.temperature}°C` : (disk.temperature ? `${disk.temperature}°C` : '-')}
                                        </span>
                                    </div>
                                </div>

                                {/* Power-on time */}
                                <div className="p-3.5 rounded-xl bg-gray-50 dark:bg-zinc-800/50 border border-gray-100 dark:border-zinc-800">
                                    <span className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-zinc-500 font-semibold">
                                        {t('disks.smart.power_on_time', 'Power-on Hours')}
                                    </span>
                                    <div className="flex items-center gap-1.5 mt-1">
                                        <Clock className="w-4 h-4 text-sky-500" />
                                        <span className="font-semibold text-gray-900 dark:text-white text-sm font-mono">
                                            {smartData?.poweron_time?.hours ? `${smartData.poweron_time.hours}h` : '-'}
                                        </span>
                                    </div>
                                </div>

                                {/* SMART Enabled */}
                                <div className="p-3.5 rounded-xl bg-gray-50 dark:bg-zinc-800/50 border border-gray-100 dark:border-zinc-800">
                                    <span className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-zinc-500 font-semibold">
                                        {t('disks.smart.support', 'Support & Enabled')}
                                    </span>
                                    <div className="flex items-center gap-1.5 mt-1 text-emerald-600 dark:text-emerald-400 font-medium">
                                        <CheckCircle2 className="w-4 h-4" />
                                        <span>{t('disks.smart.enabled', 'Active')}</span>
                                    </div>
                                </div>
                            </div>

                            {/* Attributes Table */}
                            {smartData?.attributes && smartData.attributes.length > 0 && (
                                <div>
                                    <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
                                        {t('disks.smart.attributes_title', 'Health Attributes')}
                                    </h4>
                                    <div className="border border-gray-100 dark:border-zinc-800 rounded-xl overflow-x-auto">
                                        <table className="w-full text-left text-xs">
                                            <thead className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-zinc-500 bg-gray-50 dark:bg-zinc-800/60 border-b border-gray-100 dark:border-zinc-800">
                                                <tr>
                                                    <th className="py-2.5 px-3">ID</th>
                                                    <th className="py-2.5 px-3">{t('disks.smart.attr_name', 'Attribute')}</th>
                                                    <th className="py-2.5 px-3">{t('disks.smart.attr_value', 'Value')}</th>
                                                    <th className="py-2.5 px-3">{t('disks.smart.attr_worst', 'Worst')}</th>
                                                    <th className="py-2.5 px-3">{t('disks.smart.attr_thresh', 'Threshold')}</th>
                                                    <th className="py-2.5 px-3">{t('disks.smart.attr_failed', 'When Failed')}</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-100 dark:divide-zinc-800/50">
                                                {smartData.attributes.map(item => {
                                                    const isHealthy = item.value >= item.thresh;
                                                    return (
                                                        <tr key={item.id} className="hover:bg-gray-50/50 dark:hover:bg-zinc-800/30">
                                                            <td className="py-2 px-3 font-mono text-gray-500">{item.id}</td>
                                                            <td className="py-2 px-3 font-medium text-gray-900 dark:text-zinc-200">{item.name}</td>
                                                            <td className="py-2 px-3 font-mono">
                                                                <span
                                                                    className={`px-1.5 py-0.5 rounded text-[11px] font-semibold ${
                                                                        isHealthy
                                                                            ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
                                                                            : 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400'
                                                                    }`}
                                                                >
                                                                    {item.value}
                                                                </span>
                                                            </td>
                                                            <td className="py-2 px-3 font-mono text-gray-600 dark:text-zinc-400">{item.worst}</td>
                                                            <td className="py-2 px-3 font-mono text-gray-600 dark:text-zinc-400">{item.thresh}</td>
                                                            <td className="py-2 px-3 text-gray-400">{item.when_failed || '-'}</td>
                                                        </tr>
                                                    );
                                                })}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}

                            {/* Self-Test Execution */}
                            <div className="pt-2 border-t border-gray-100 dark:border-zinc-800">
                                <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
                                    {t('disks.smart.run_test', 'Run Disk Health Test')}
                                </h4>
                                <div className="grid grid-cols-2 gap-3">
                                    <button
                                        type="button"
                                        onClick={() => handleRunTest('short')}
                                        disabled={testLoading !== null}
                                        className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-xs text-emerald-700 bg-emerald-50 dark:bg-emerald-950/40 hover:bg-emerald-100 border border-emerald-200 dark:border-emerald-800/60 disabled:opacity-50 transition-colors cursor-pointer"
                                    >
                                        <Play className="w-3.5 h-3.5" />
                                        <span>{t('disks.smart.quick_test', 'Run Quick Test (~2 min)')}</span>
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => handleRunTest('long')}
                                        disabled={testLoading !== null}
                                        className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-xs text-amber-700 bg-amber-50 dark:bg-amber-950/40 hover:bg-amber-100 border border-amber-200 dark:border-amber-800/60 disabled:opacity-50 transition-colors cursor-pointer"
                                    >
                                        <Play className="w-3.5 h-3.5" />
                                        <span>{t('disks.smart.long_test', 'Run Extended Test')}</span>
                                    </button>
                                </div>
                            </div>
                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="flex justify-end p-4 bg-gray-50 dark:bg-zinc-800/50 border-t border-gray-100 dark:border-zinc-800">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-xs font-semibold rounded-xl bg-white dark:bg-zinc-800 text-gray-700 dark:text-zinc-200 border border-gray-200 dark:border-zinc-700 hover:bg-gray-50 transition-colors cursor-pointer"
                    >
                        {t('common.close', 'Close')}
                    </button>
                </div>
            </div>
        </div>
    );
}
