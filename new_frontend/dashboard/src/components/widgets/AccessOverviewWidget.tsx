import { Terminal, Check, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { RemoteServiceItem } from '../../types/dashboard';

interface AccessOverviewWidgetProps {
    services: RemoteServiceItem[];
}

export default function AccessOverviewWidget({ services }: AccessOverviewWidgetProps) {
    const { t } = useTranslation();

    const activeCount = services.filter(s => s.active).length;

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 flex flex-col justify-between transition-all hover:shadow-md">
            <div>
                <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400">
                            <Terminal className="w-5 h-5" />
                        </div>
                        <div>
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                                {t('widgets.access.title', 'Remote Services')}
                            </h3>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {activeCount} / {services.length} {t('widgets.access.running', 'Active')}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-2 max-h-56 overflow-y-auto pr-1">
                    {services.length === 0 ? (
                        <p className="col-span-2 text-xs text-gray-400 dark:text-zinc-500 py-4 text-center">
                            {t('widgets.access.no_services', 'No access services available')}
                        </p>
                    ) : (
                        services.map((svc) => (
                            <div
                                key={svc.id}
                                className="flex items-center justify-between p-2.5 rounded-xl bg-gray-50 dark:bg-zinc-800/60 border border-gray-100 dark:border-zinc-800"
                            >
                                <span className="text-xs font-semibold text-gray-800 dark:text-zinc-200 truncate">
                                    {svc.name}
                                </span>
                                <span
                                    className={`inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded ${
                                        svc.active
                                            ? 'bg-emerald-100/70 text-emerald-700 dark:bg-emerald-950/70 dark:text-emerald-400'
                                            : 'bg-zinc-200 dark:bg-zinc-700/60 text-zinc-500 dark:text-zinc-400'
                                    }`}
                                >
                                    {svc.active ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
                                    {svc.active ? t('widgets.access.running', 'ON') : t('widgets.access.stopped', 'OFF')}
                                </span>
                            </div>
                        ))
                    )}
                </div>
            </div>

            <div className="mt-4 pt-3 border-t border-gray-100 dark:border-zinc-800/80 text-xs text-gray-500 dark:text-zinc-400 flex justify-between">
                <span>{t('widgets.access.active_count', 'Configured Services')}</span>
                <span className="font-semibold text-gray-900 dark:text-white">
                    {services.length}
                </span>
            </div>
        </div>
    );
}
