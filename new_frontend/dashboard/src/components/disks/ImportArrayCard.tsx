import { useState } from 'react';
import { Download, AlertTriangle, Key, HardDrive } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { ImportablePool } from '../../types/dashboard';

interface ImportArrayCardProps {
    pool: ImportablePool;
    onImport: (poolName: string, keyFile?: File | null) => void;
    isLoading?: boolean;
}

export default function ImportArrayCard({
    pool,
    onImport,
    isLoading = false
}: ImportArrayCardProps) {
    const { t } = useTranslation();
    const [keyFile, setKeyFile] = useState<File | null>(null);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onImport(pool.name, keyFile);
    };

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 transition-all hover:shadow-md">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400">
                        <Download className="w-5 h-5" />
                    </div>
                    <div>
                        <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                            {t('disks.import.title', 'Import Existing Array')} ({pool.name})
                        </h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                            {t('disks.import.subtitle', 'Detected pre-existing disk array')}
                        </p>
                    </div>
                </div>

                {pool.state !== 'ONLINE' && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 border border-amber-200">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        {pool.state}
                    </span>
                )}
            </div>

            <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
                <div>
                    <p className="text-gray-600 dark:text-zinc-400 mb-2">
                        {t('disks.import.disks_belong', 'The following disks belong to the existing array {{name}}:', {
                            name: pool.name
                        })}
                    </p>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                        {pool.disks.map((d, i) => (
                            <div
                                key={i}
                                className="flex items-center gap-2 p-2 rounded-lg bg-gray-50 dark:bg-zinc-800/50 border border-gray-100 dark:border-zinc-800 font-mono text-[11px]"
                            >
                                <HardDrive className="w-3.5 h-3.5 text-gray-500" />
                                <span>{d}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Optional Key File */}
                <div className="p-3.5 rounded-xl bg-gray-50 dark:bg-zinc-800/40 border border-gray-200/70 dark:border-zinc-700 space-y-2">
                    <label className="flex items-center gap-1.5 font-medium text-gray-700 dark:text-zinc-300">
                        <Key className="w-3.5 h-3.5 text-amber-500" />
                        <span>{t('disks.import.key_label', 'Encryption Key (if encrypted)')}</span>
                    </label>
                    <input
                        type="file"
                        onChange={e => setKeyFile(e.target.files?.[0] || null)}
                        className="block w-full text-xs text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-indigo-50 file:text-indigo-700 dark:file:bg-indigo-950/60 dark:file:text-indigo-400 hover:file:bg-indigo-100 cursor-pointer"
                    />
                    <p className="text-[11px] text-gray-400 dark:text-zinc-500 leading-normal">
                        {t(
                            'disks.import.key_help',
                            'If this disk array was encrypted, upload the key file. If unencrypted, leave this empty.'
                        )}
                    </p>
                </div>

                <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-xs text-white bg-blue-600 hover:bg-blue-500 shadow-md shadow-blue-600/20 disabled:opacity-50 transition-all cursor-pointer"
                >
                    <Download className="w-4 h-4" />
                    {isLoading
                        ? t('disks.import.importing', 'Importing Array...')
                        : t('disks.import.submit', 'Import {{name}}', { name: pool.name })}
                </button>
            </form>
        </div>
    );
}

