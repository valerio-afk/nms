import { Construction, ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface PlaceholderPageProps {
    title: string;
    onBack: () => void;
}

export default function PlaceholderPage({ title, onBack }: PlaceholderPageProps) {
    const { t } = useTranslation();

    return (
        <div className="flex flex-col items-center justify-center p-12 text-center bg-white dark:bg-zinc-900 rounded-2xl shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 min-h-[400px]">
            <div className="w-16 h-16 rounded-2xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mb-6">
                <Construction className="w-8 h-8" />
            </div>

            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                {title}
            </h2>
            <p className="mt-2 text-sm text-gray-500 dark:text-zinc-400 max-w-md">
                This module is scheduled for conversion in the next phase. The core login authentication and dashboard overview are operational.
            </p>

            <button
                onClick={onBack}
                className="mt-6 inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-md shadow-indigo-500/20 transition-all cursor-pointer"
            >
                <ArrowLeft className="w-4 h-4" />
                <span>{t('actions.back_to_dashboard', 'Back to Dashboard')}</span>
            </button>
        </div>
    );
}
