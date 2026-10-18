import { useState, useEffect, useCallback } from 'react';
import { RotateCw, ShieldCheck, Activity } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { User } from '@nms/shared';
import type { DashboardMetrics } from '../types/dashboard';
import { fetchDashboardMetrics } from '../utils/api';
import DiskUsageWidget from '../components/widgets/DiskUsageWidget';
import DiskOverviewWidget from '../components/widgets/DiskOverviewWidget';
import NetworkOverviewWidget from '../components/widgets/NetworkOverviewWidget';
import AccessOverviewWidget from '../components/widgets/AccessOverviewWidget';
import SystemInfoWidget from '../components/widgets/SystemInfoWidget';
import SensorsWidget from '../components/widgets/SensorsWidget';

interface DashboardPageProps {
    currentUser: User | null;
}

export default function DashboardPage({ currentUser }: DashboardPageProps) {
    const { t } = useTranslation();
    const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadMetrics = useCallback(async (isManualRefresh = false) => {
        if (isManualRefresh) setRefreshing(true);
        setError(null);
        try {
            const data = await fetchDashboardMetrics();
            setMetrics(data);
        } catch (err: any) {
            console.error('Failed to load dashboard metrics', err);
            setError(err?.message || t('dashboard.error_loading', 'Failed to retrieve metrics'));
        } finally {
            setLoading(false);
            if (isManualRefresh) setRefreshing(false);
        }
    }, [t]);

    useEffect(() => {
        loadMetrics();
        // Auto-refresh metrics every 15 seconds
        const timer = setInterval(() => {
            loadMetrics();
        }, 15000);
        return () => clearInterval(timer);
    }, [loadMetrics]);

    const displayName = currentUser?.visible_name || currentUser?.username || 'Admin';

    return (
        <div className="space-y-6">
            {/* Top Welcome & Summary Banner */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gradient-to-r from-indigo-500/10 via-purple-500/5 to-transparent p-6 rounded-2xl ring-1 ring-indigo-500/20 dark:ring-indigo-500/30">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-indigo-600 dark:bg-indigo-500 text-white flex items-center justify-center shadow-md shadow-indigo-500/25">
                        <Activity className="w-6 h-6" />
                    </div>
                    <div>
                        <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">
                            {t('dashboard.welcome', 'Welcome')}, {displayName}.
                        </h2>
                        <div className="flex items-center gap-2 mt-1 text-xs text-gray-600 dark:text-zinc-400">
                            <ShieldCheck className="w-4 h-4 text-emerald-500" />
                            <span>{t('dashboard.system_status', 'System is healthy and operational')}</span>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <button
                        onClick={() => loadMetrics(true)}
                        disabled={refreshing}
                        className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl bg-white dark:bg-zinc-800 text-gray-700 dark:text-zinc-200 border border-gray-200 dark:border-zinc-700 hover:bg-gray-50 dark:hover:bg-zinc-700/60 shadow-xs transition-all cursor-pointer"
                    >
                        <RotateCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                        <span>{refreshing ? t('dashboard.refreshing', 'Refreshing...') : t('dashboard.refresh', 'Refresh')}</span>
                    </button>
                </div>
            </div>

            {error && (
                <div className="p-4 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 text-red-600 dark:text-red-400 text-sm">
                    {error}
                </div>
            )}

            {/* Widgets Grid */}
            {loading && !metrics ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-pulse">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                        <div key={i} className="h-64 rounded-2xl bg-gray-200 dark:bg-zinc-800/60" />
                    ))}
                </div>
            ) : metrics ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <DiskUsageWidget pool={metrics.pool} userQuota={currentUser?.quota} />
                    <DiskOverviewWidget disks={metrics.disks} />
                    <NetworkOverviewWidget networks={metrics.networks} />
                    <AccessOverviewWidget services={metrics.services} />
                    <SystemInfoWidget system={metrics.system} />
                    <SensorsWidget sensors={metrics.sensors} />
                </div>
            ) : null}
        </div>
    );
}
