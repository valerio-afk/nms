import { Camera, RotateCcw, Trash2, Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { SnapshotItem } from '../../types/dashboard';
import { formatBytes } from '../../utils/formatters';

interface SnapshotsCardProps {
    snapshots: SnapshotItem[];
    onRollback: (snapshotName: string) => void;
    onDelete: (snapshotName: string) => void;
    onCreateSnapshot: () => void;
    isLoading?: boolean;
}

export default function SnapshotsCard({
    snapshots,
    onRollback,
    onDelete,
    onCreateSnapshot,
    isLoading = false
}: SnapshotsCardProps) {
    const { t } = useTranslation();

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 transition-all hover:shadow-md">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400">
                        <Camera className="w-5 h-5" />
                    </div>
                    <div>
                        <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                            {t('disks.snapshots.title', 'Snapshots')}
                        </h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                            {snapshots.length} {t('disks.snapshots.count', 'recorded points')}
                        </p>
                    </div>
                </div>

                <button
                    type="button"
                    onClick={onCreateSnapshot}
                    disabled={isLoading}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl bg-purple-600 text-white hover:bg-purple-500 shadow-xs cursor-pointer transition-colors"
                >
                    <Plus className="w-3.5 h-3.5" />
                    <span>{t('disks.snapshots.new', 'New Snapshot')}</span>
                </button>
            </div>

            {/* List */}
            {snapshots.length === 0 ? (
                <div className="py-8 text-center text-xs text-gray-400 dark:text-zinc-500">
                    <Camera className="w-8 h-8 mx-auto mb-2 opacity-40 text-gray-400" />
                    <p>{t('disks.snapshots.empty', 'No snapshots have been taken yet.')}</p>
                </div>
            ) : (
                <div className="mt-4 overflow-x-auto">
                    <table className="w-full text-xs text-left">
                        <thead className="text-[11px] uppercase tracking-wider text-gray-400 dark:text-zinc-500 border-b border-gray-100 dark:border-zinc-800">
                            <tr>
                                <th className="pb-2.5 font-medium">{t('disks.snapshots.name', 'Snapshot Name')}</th>
                                <th className="pb-2.5 font-medium">{t('disks.snapshots.ref_size', 'Ref. Size')}</th>
                                <th className="pb-2.5 font-medium text-right">{t('disks.snapshots.actions', 'Actions')}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100 dark:divide-zinc-800/60">
                            {snapshots.map(s => (
                                <tr key={s.name} className="hover:bg-gray-50 dark:hover:bg-zinc-800/40 transition-colors">
                                    <td className="py-2.5 font-mono font-medium text-gray-900 dark:text-zinc-200">
                                        {s.name}
                                    </td>
                                    <td className="py-2.5 text-gray-600 dark:text-zinc-300 font-medium">
                                        {formatBytes(s.ref_size)}
                                    </td>
                                    <td className="py-2.5 text-right space-x-1.5">
                                        <button
                                            type="button"
                                            onClick={() => onRollback(s.name)}
                                            title={t('disks.snapshots.rollback_tooltip', 'Rollback to this snapshot')}
                                            className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900/60 transition-colors cursor-pointer"
                                        >
                                            <RotateCcw className="w-3.5 h-3.5" />
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => onDelete(s.name)}
                                            title={t('disks.snapshots.delete_tooltip', 'Delete snapshot')}
                                            className="p-1.5 rounded-lg bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/60 transition-colors cursor-pointer"
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
