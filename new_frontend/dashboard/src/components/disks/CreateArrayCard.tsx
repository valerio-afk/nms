import { useState } from 'react';
import { PlusCircle, Shield, Lock, Archive, ChevronDown, ChevronUp, HardDrive, Check, HelpCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { DiskItem, CreatePoolPayload } from '../../types/dashboard';
import { formatBytes } from '../../utils/formatters';

interface CreateArrayCardProps {
    availableDisks: DiskItem[];
    onCreatePool: (payload: CreatePoolPayload) => void;
    isLoading?: boolean;
}

export default function CreateArrayCard({
    availableDisks,
    onCreatePool,
    isLoading = false
}: CreateArrayCardProps) {
    const { t } = useTranslation();

    const [redundancy, setRedundancy] = useState(false);
    const [encryption, setEncryption] = useState(false);
    const [compression, setCompression] = useState(false);

    const [showAdvanced, setShowAdvanced] = useState(false);
    const [poolName, setPoolName] = useState('tank');
    const [datasetName, setDatasetName] = useState('data');

    // Default select all available disks
    const [selectedDisks, setSelectedDisks] = useState<string[]>(() =>
        availableDisks.map(d => d.path || (d.name ? `/dev/${d.name}` : d.name))
    );

    const toggleDiskSelection = (path: string) => {
        setSelectedDisks(prev =>
            prev.includes(path) ? prev.filter(p => p !== path) : [...prev, path]
        );
    };

    // Redundancy requires at least 3 disks
    const redundancyDisabled = selectedDisks.length <= 2;

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (selectedDisks.length === 0) return;
        // redundancyDisabled is a guard — but double-check in case state is stale
        const effectiveRedundancy = redundancy && !redundancyDisabled;
        if (effectiveRedundancy && selectedDisks.length < 3) {
            alert(t('disks.create.min_disks_error', 'Redundancy requires a minimum of 3 disks'));
            return;
        }

        onCreatePool({
            pool_name: poolName.trim() || 'tank',
            dataset_name: datasetName.trim() || 'data',
            redundancy: effectiveRedundancy,
            encryption,
            compression,
            disks: selectedDisks
        });
    };

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 transition-all">
            {/* Header */}
            <div className="flex items-center gap-3 pb-4 border-b border-gray-100 dark:border-zinc-800">
                <div className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400">
                    <PlusCircle className="w-5 h-5" />
                </div>
                <div>
                    <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                        {t('disks.create.title', 'Create New Array')}
                    </h3>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                        {t('disks.create.subtitle', 'Configure a unified storage array with your disks')}
                    </p>
                </div>
            </div>

            <form onSubmit={handleSubmit} className="mt-5 space-y-5">
                {/* Switches */}
                <div className="space-y-4">
                    {/* Redundancy */}
                    <div className={`flex items-center justify-between p-3.5 rounded-xl border transition-all ${
                        redundancyDisabled
                            ? 'bg-gray-50/50 dark:bg-zinc-800/20 border-gray-100 dark:border-zinc-800 opacity-50'
                            : 'bg-gray-50 dark:bg-zinc-800/50 border-gray-100 dark:border-zinc-800'
                    }`}>
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400">
                                <Shield className="w-4 h-4" />
                            </div>
                            <div>
                                <div className="flex items-center gap-1.5">
                                    <span className="text-sm font-medium text-gray-900 dark:text-zinc-100">
                                        {t('disks.create.redundancy', 'Redundancy')}
                                    </span>
                                    <span
                                        className="text-gray-400 hover:text-gray-600 dark:hover:text-zinc-200 cursor-help"
                                        title={t(
                                            'disks.create.redundancy_tip',
                                            'Protects data by distributing it across multiple disks, allowing recovery if a single disk fails. Requires minimum 3 disks.'
                                        )}
                                    >
                                        <HelpCircle className="w-3.5 h-3.5" />
                                    </span>
                                </div>
                                <p className="text-xs text-gray-500 dark:text-zinc-400 mt-0.5">
                                    {redundancyDisabled
                                        ? t('disks.create.redundancy_needs_disks', 'Select at least 3 drives to enable')
                                        : t('disks.create.redundancy_desc', 'Protects data against single disk failure')}
                                </p>
                            </div>
                        </div>
                        <label className={`relative inline-flex items-center ${redundancyDisabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
                            <input
                                type="checkbox"
                                checked={redundancy && !redundancyDisabled}
                                onChange={e => !redundancyDisabled && setRedundancy(e.target.checked)}
                                disabled={redundancyDisabled}
                                className="sr-only peer"
                            />
                            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600" />
                        </label>
                    </div>

                    {/* Encryption */}
                    <div className="flex items-center justify-between p-3.5 rounded-xl bg-gray-50 dark:bg-zinc-800/50 border border-gray-100 dark:border-zinc-800">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400">
                                <Lock className="w-4 h-4" />
                            </div>
                            <div>
                                <div className="flex items-center gap-1.5">
                                    <span className="text-sm font-medium text-gray-900 dark:text-zinc-100">
                                        {t('disks.create.encryption', 'Encryption')}
                                    </span>
                                    <span
                                        className="text-gray-400 hover:text-gray-600 dark:hover:text-zinc-200 cursor-help"
                                        title={t(
                                            'disks.create.encryption_tip',
                                            'Secures data by encoding it so only authorised users with the key can access the information stored on your array.'
                                        )}
                                    >
                                        <HelpCircle className="w-3.5 h-3.5" />
                                    </span>
                                </div>
                                <p className="text-xs text-gray-500 dark:text-zinc-400 mt-0.5">
                                    {t('disks.create.encryption_desc', 'Secures data with encryption protection')}
                                </p>
                            </div>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input
                                type="checkbox"
                                checked={encryption}
                                onChange={e => setEncryption(e.target.checked)}
                                className="sr-only peer"
                            />
                            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600" />
                        </label>
                    </div>

                    {/* Compression */}
                    <div className="flex items-center justify-between p-3.5 rounded-xl bg-gray-50 dark:bg-zinc-800/50 border border-gray-100 dark:border-zinc-800">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-sky-50 dark:bg-sky-950/40 text-sky-600 dark:text-sky-400">
                                <Archive className="w-4 h-4" />
                            </div>
                            <div>
                                <div className="flex items-center gap-1.5">
                                    <span className="text-sm font-medium text-gray-900 dark:text-zinc-100">
                                        {t('disks.create.compression', 'Compression')}
                                    </span>
                                    <span
                                        className="text-gray-400 hover:text-gray-600 dark:hover:text-zinc-200 cursor-help"
                                        title={t(
                                            'disks.create.compression_tip',
                                            'Reduces storage space by automatically compressing data before writing it to disk, saving disk space.'
                                        )}
                                    >
                                        <HelpCircle className="w-3.5 h-3.5" />
                                    </span>
                                </div>
                                <p className="text-xs text-gray-500 dark:text-zinc-400 mt-0.5">
                                    {t('disks.create.compression_desc', 'Automatically compresses data to save disk space')}
                                </p>
                            </div>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input
                                type="checkbox"
                                checked={compression}
                                onChange={e => setCompression(e.target.checked)}
                                className="sr-only peer"
                            />
                            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600" />
                        </label>
                    </div>
                </div>

                {/* Advanced Options Toggle */}
                <div className="border border-gray-200 dark:border-zinc-800 rounded-xl overflow-hidden">
                    <button
                        type="button"
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className="w-full flex items-center justify-between p-3.5 bg-gray-50 dark:bg-zinc-800/40 text-xs font-semibold text-gray-700 dark:text-zinc-300 hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                    >
                        <span>{t('disks.create.advanced_options', 'Advanced Options')}</span>
                        {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>

                    {showAdvanced && (
                        <div className="p-4 space-y-4 bg-white dark:bg-zinc-900 border-t border-gray-200 dark:border-zinc-800 text-xs">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div>
                                    <label className="block font-medium text-gray-700 dark:text-zinc-300 mb-1">
                                        {t('disks.create.pool_name', 'Array Name')}
                                    </label>
                                    <input
                                        type="text"
                                        value={poolName}
                                        onChange={e => setPoolName(e.target.value)}
                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white font-mono text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block font-medium text-gray-700 dark:text-zinc-300 mb-1">
                                        {t('disks.create.dataset_name', 'Dataset Name')}
                                    </label>
                                    <input
                                        type="text"
                                        value={datasetName}
                                        onChange={e => setDatasetName(e.target.value)}
                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white font-mono text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                                    />
                                </div>
                            </div>

                            {/* Disk Picker */}
                            <div>
                                <label className="block font-medium text-gray-700 dark:text-zinc-300 mb-2">
                                    {t('disks.create.select_disks', 'Target Disks')} ({selectedDisks.length}/{availableDisks.length})
                                </label>
                                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                                    {availableDisks.map((d, i) => {
                                        const dPath = d.path || (d.name ? `/dev/${d.name}` : d.name);
                                        const isSelected = selectedDisks.includes(dPath);
                                        return (
                                            <div
                                                key={dPath || i}
                                                onClick={() => toggleDiskSelection(dPath)}
                                                className={`flex items-center justify-between p-2.5 rounded-lg border cursor-pointer transition-colors ${
                                                    isSelected
                                                        ? 'bg-indigo-50/70 dark:bg-indigo-950/40 border-indigo-300 dark:border-indigo-800'
                                                        : 'bg-gray-50 dark:bg-zinc-800/40 border-gray-200 dark:border-zinc-700'
                                                }`}
                                            >
                                                <div className="flex items-center gap-2">
                                                    <div
                                                        className={`w-4 h-4 rounded border flex items-center justify-center text-white text-[10px] ${
                                                            isSelected
                                                                ? 'bg-indigo-600 border-indigo-600'
                                                                : 'border-gray-300 dark:border-zinc-600'
                                                        }`}
                                                    >
                                                        {isSelected && <Check className="w-3 h-3" />}
                                                    </div>
                                                    <HardDrive className="w-3.5 h-3.5 text-gray-500" />
                                                    <span className="font-medium text-gray-900 dark:text-zinc-100">
                                                        {d.model || d.name}
                                                    </span>
                                                    <span className="font-mono text-gray-400 dark:text-zinc-500 text-[11px]">
                                                        ({dPath})
                                                    </span>
                                                </div>
                                                <span className="font-semibold text-gray-700 dark:text-zinc-300">
                                                    {d.size ? formatBytes(d.size) : '-'}
                                                </span>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Submit button */}
                <button
                    type="submit"
                    disabled={isLoading || selectedDisks.length === 0}
                    className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm text-white bg-indigo-600 hover:bg-indigo-500 shadow-md shadow-indigo-600/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer"
                >
                    <PlusCircle className="w-4 h-4" />
                    {isLoading
                        ? t('disks.create.creating', 'Creating Array...')
                        : t('disks.create.submit', 'Create Array')}
                </button>
            </form>
        </div>
    );
}
