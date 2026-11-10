import { useState } from 'react';
import { PlusCircle, AlertTriangle, HardDrive, Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { DiskItem } from '../../types/dashboard';
import { formatBytes } from '../../utils/formatters';

interface AddDisksCardProps {
    attachableDisks: DiskItem[];
    onAddDisk: (diskPath: string) => void;
    isLoading?: boolean;
}

export default function AddDisksCard({
    attachableDisks,
    onAddDisk,
    isLoading = false
}: AddDisksCardProps) {
    const { t } = useTranslation();

    const [selectedPath, setSelectedPath] = useState<string>(() => {
        if (attachableDisks.length > 0) {
            return attachableDisks[0].path || (attachableDisks[0].name ? `/dev/${attachableDisks[0].name}` : '');
        }
        return '';
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedPath) return;
        onAddDisk(selectedPath);
    };

    if (attachableDisks.length === 0) return null;

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 transition-all">
            {/* Header */}
            <div className="flex items-center gap-3 pb-4 border-b border-gray-100 dark:border-zinc-800">
                <div className="p-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400">
                    <PlusCircle className="w-5 h-5" />
                </div>
                <div>
                    <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                        {t('disks.add.title', 'Add Disk to Array')}
                    </h3>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                        {t('disks.add.subtitle', 'Expand your storage capacity by attaching unassigned disks')}
                    </p>
                </div>
            </div>

            {/* Warning Box */}
            <div className="mt-4 p-4 rounded-xl bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50 text-xs text-amber-800 dark:text-amber-300 space-y-2">
                <div className="flex items-center gap-2 font-semibold text-amber-900 dark:text-amber-200">
                    <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600 dark:text-amber-400" />
                    <span>{t('disks.add.warning_title', 'Important Notice Regarding Array Expansion')}</span>
                </div>
                <ul className="list-disc list-inside space-y-1 text-amber-800 dark:text-amber-300/90 pl-1">
                    <li>{t('disks.add.warning_1', 'This operation expands the disk array. Ensure your critical data is backed up.')}</li>
                    <li>{t('disks.add.warning_2', 'Depending on the array size, expansion and balancing may take several hours.')}</li>
                    <li>{t('disks.add.warning_3', 'Do not power off or disconnect the device while expansion is in progress.')}</li>
                </ul>
            </div>

            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
                <label className="block text-xs font-semibold text-gray-700 dark:text-zinc-300">
                    {t('disks.add.choose_disk', 'Select an unassigned disk to attach:')}
                </label>

                <div className="space-y-2 max-h-48 overflow-y-auto">
                    {attachableDisks.map((d, i) => {
                        const path = d.path || (d.name ? `/dev/${d.name}` : '');
                        const isSelected = selectedPath === path;
                        return (
                            <div
                                key={path || i}
                                onClick={() => setSelectedPath(path)}
                                className={`flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-colors ${
                                    isSelected
                                        ? 'bg-amber-50/60 dark:bg-amber-950/30 border-amber-300 dark:border-amber-800'
                                        : 'bg-gray-50 dark:bg-zinc-800/40 border-gray-200 dark:border-zinc-700'
                                }`}
                            >
                                <div className="flex items-center gap-2.5">
                                    <div
                                        className={`w-4 h-4 rounded-full border flex items-center justify-center text-white text-[10px] ${
                                            isSelected
                                                ? 'bg-amber-600 border-amber-600'
                                                : 'border-gray-300 dark:border-zinc-600'
                                        }`}
                                    >
                                        {isSelected && <Check className="w-2.5 h-2.5" />}
                                    </div>
                                    <HardDrive className="w-4 h-4 text-gray-500" />
                                    <div>
                                        <p className="text-xs font-medium text-gray-900 dark:text-zinc-100">
                                            {d.model || d.name}
                                        </p>
                                        <p className="font-mono text-[11px] text-gray-400 dark:text-zinc-500">
                                            {path}
                                        </p>
                                    </div>
                                </div>
                                <span className="text-xs font-semibold text-gray-700 dark:text-zinc-300">
                                    {d.size ? formatBytes(d.size) : '-'}
                                </span>
                            </div>
                        );
                    })}
                </div>

                <button
                    type="submit"
                    disabled={!selectedPath || isLoading}
                    className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-xs text-white bg-amber-600 hover:bg-amber-500 shadow-md shadow-amber-600/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
                >
                    <PlusCircle className="w-4 h-4" />
                    {isLoading
                        ? t('disks.add.expanding', 'Expanding Pool...')
                        : t('disks.add.submit', 'Add Disk to Array')}
                </button>
            </form>
        </div>
    );
}

