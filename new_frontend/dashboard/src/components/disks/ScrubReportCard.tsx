import { ShieldCheck, Clock } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { ScrubReport } from '../../types/dashboard';

interface ScrubReportCardProps {
    report: ScrubReport;
}

export default function ScrubReportCard({ report }: ScrubReportCardProps) {
    const { t } = useTranslation();

    const hasErrors = report.errors !== '0' && report.errors !== '-' && report.errors !== 'none';

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 transition-all hover:shadow-md">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                <div className="flex items-center gap-3">
                    <div
                        className={`p-2.5 rounded-xl ${
                            hasErrors
                                ? 'bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400'
                                : 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400'
                        }`}
                    >
                        <ShieldCheck className="w-5 h-5" />
                    </div>
                    <div>
                        <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                            {t('disks.scrub.report_title', 'Last Verification Report')}
                        </h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                            {t('disks.scrub.report_subtitle', 'Disk integrity verification outcome')}
                        </p>
                    </div>
                </div>

                <span
                    className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        hasErrors
                            ? 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400 border border-red-200 dark:border-red-800/50'
                            : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/50'
                    }`}
                >
                    {hasErrors ? t('disks.scrub.issues_found', 'Issues Found') : t('disks.scrub.passed', 'Passed')}
                </span>
            </div>

            {/* Metrics List */}
            <div className="mt-4 space-y-2.5 text-xs">
                <div className="flex justify-between items-center">
                    <span className="text-gray-500 dark:text-zinc-400 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        {t('disks.scrub.started_at', 'Started at')}:
                    </span>
                    <span className="font-mono text-gray-900 dark:text-zinc-200">
                        {report.started}
                    </span>
                </div>

                <div className="flex justify-between items-center">
                    <span className="text-gray-500 dark:text-zinc-400 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        {t('disks.scrub.ended_at', 'Ended at')}:
                    </span>
                    <span className="font-mono text-gray-900 dark:text-zinc-200">
                        {report.ended}
                    </span>
                </div>

                <div className="flex justify-between items-center pt-2 border-t border-gray-100 dark:border-zinc-800">
                    <span className="text-gray-500 dark:text-zinc-400">
                        {t('disks.scrub.errors', 'Errors')}:
                    </span>
                    <span
                        className={`font-mono font-semibold ${
                            hasErrors ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'
                        }`}
                    >
                        {report.errors}
                    </span>
                </div>
            </div>
        </div>
    );
}
