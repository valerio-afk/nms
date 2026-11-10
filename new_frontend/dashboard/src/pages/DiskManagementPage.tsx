import { useState, useEffect, useCallback } from 'react';
import {
    HardDrive,
    RotateCw,
    ArrowLeft,
    AlertTriangle,
    Database,
    Shield,
    Lock,
    Archive
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type {
    DiskItem,
    PoolStatus,
    SnapshotItem,
    ScrubReport,
    ScrubInfo,
    ImportablePool,
    CreatePoolPayload
} from '../types/dashboard';
import {
    fetchDisks,
    fetchPoolStatus,
    fetchAttachableDisks,
    fetchImportablePools,
    fetchScrubInfo,
    fetchLastScrubReport,
    fetchSnapshots,
    mountPool,
    unmountPool,
    startScrub,
    createSnapshot,
    deleteSnapshot,
    rollbackSnapshot,
    createPool,
    expandPool,
    formatDisk
} from '../utils/api';
import { formatBytes, formatPercent } from '../utils/formatters';
import DiskCard from '../components/disks/DiskCard';
import DiskToolsCard from '../components/disks/DiskToolsCard';
import CreateArrayCard from '../components/disks/CreateArrayCard';
import AddDisksCard from '../components/disks/AddDisksCard';
import SnapshotsCard from '../components/disks/SnapshotsCard';
import ScrubReportCard from '../components/disks/ScrubReportCard';
import ImportArrayCard from '../components/disks/ImportArrayCard';
import SmartModal from '../components/disks/SmartModal';
import ConfirmModal from '../components/ConfirmModal';

interface DiskManagementPageProps {
    onNavigate?: (tab: string) => void;
}

export default function DiskManagementPage({ onNavigate }: DiskManagementPageProps) {
    const { t } = useTranslation();

    // Data states
    const [disks, setDisks] = useState<DiskItem[]>([]);
    const [pool, setPool] = useState<PoolStatus | null>(null);
    const [attachableDisks, setAttachableDisks] = useState<DiskItem[]>([]);
    const [importablePools, setImportablePools] = useState<ImportablePool[]>([]);
    const [scrubInfo, setScrubInfo] = useState<ScrubInfo | null>(null);
    const [scrubReport, setScrubReport] = useState<ScrubReport | null>(null);
    const [snapshots, setSnapshots] = useState<SnapshotItem[]>([]);

    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Selected disk for SMART diagnostic modal
    const [selectedSmartDisk, setSelectedSmartDisk] = useState<DiskItem | null>(null);

    // Confirmation modal state
    const [confirmModal, setConfirmModal] = useState<{
        isOpen: boolean;
        title: string;
        message: string;
        confirmText: string;
        variant: 'danger' | 'warning' | 'primary';
        onConfirm: () => Promise<void>;
        isLoading?: boolean;
    }>({
        isOpen: false,
        title: '',
        message: '',
        confirmText: '',
        variant: 'warning',
        onConfirm: async () => {}
    });

    // Create snapshot dialog state
    const [isSnapshotDialogOpen, setIsSnapshotDialogOpen] = useState(false);
    const [snapshotNameInput, setSnapshotNameInput] = useState('');
    const [isActionLoading, setIsActionLoading] = useState<string | null>(null);

    // Fetch all page data
    const loadData = useCallback(async (isManual = false) => {
        if (isManual) setRefreshing(true);
        try {
            const [
                disksRes,
                poolRes,
                attachableRes,
                importableRes,
                scrubInfoRes,
                scrubReportRes,
                snapshotsRes
            ] = await Promise.allSettled([
                fetchDisks(),
                fetchPoolStatus(),
                fetchAttachableDisks(),
                fetchImportablePools(),
                fetchScrubInfo(),
                fetchLastScrubReport(),
                fetchSnapshots()
            ]);

            if (disksRes.status === 'fulfilled') setDisks(disksRes.value);
            if (poolRes.status === 'fulfilled') setPool(poolRes.value);
            if (attachableRes.status === 'fulfilled') setAttachableDisks(attachableRes.value);
            if (importableRes.status === 'fulfilled') setImportablePools(importableRes.value);
            if (scrubInfoRes.status === 'fulfilled') setScrubInfo(scrubInfoRes.value);
            if (scrubReportRes.status === 'fulfilled') setScrubReport(scrubReportRes.value);
            if (snapshotsRes.status === 'fulfilled') setSnapshots(snapshotsRes.value);

            setError(null);
        } catch (err: any) {
            console.error('Failed to load disk management data', err);
            if (isManual) {
                setError(err?.message || t('disks.error_loading', 'Failed to retrieve disk information'));
            }
        } finally {
            setLoading(false);
            if (isManual) setRefreshing(false);
        }
    }, [t]);

    // Initial fetch and 3000ms background polling (matching Flask GlobalRefresher)
    useEffect(() => {
        loadData();
        const timer = setInterval(() => {
            loadData(false);
        }, 3000);
        return () => clearInterval(timer);
    }, [loadData]);

    // Handlers
    const handleToggleMount = () => {
        if (!pool) return;
        const willUnmount = pool.isMounted;
        setConfirmModal({
            isOpen: true,
            title: willUnmount
                ? t('disks.actions.unmount_title', 'Unmount Disk Array')
                : t('disks.actions.mount_title', 'Mount Disk Array'),
            message: willUnmount
                ? t(
                      'disks.actions.unmount_confirm',
                      'Are you sure you want to unmount the disk array? Any active network shares, file browser sessions, or remote access will be temporarily unavailable.'
                  )
                : t(
                      'disks.actions.mount_confirm',
                      'Mount the disk array to make your files accessible.'
                  ),
            confirmText: willUnmount
                ? t('disks.tools.unmount', 'Unmount')
                : t('disks.tools.mount', 'Mount'),
            variant: willUnmount ? 'danger' : 'primary',
            onConfirm: async () => {
                setConfirmModal(prev => ({ ...prev, isLoading: true }));
                try {
                    if (willUnmount) {
                        await unmountPool();
                    } else {
                        await mountPool();
                    }
                    await loadData(true);
                } finally {
                    setConfirmModal(prev => ({ ...prev, isOpen: false, isLoading: false }));
                }
            }
        });
    };

    const handleVerify = async () => {
        setIsActionLoading('verify');
        try {
            await startScrub();
            await loadData(true);
        } catch (err: any) {
            setError(err?.message || t('disks.scrub.error_starting', 'Failed to start disk verification.'));
        } finally {
            setIsActionLoading(null);
        }
    };

    const handleOpenCreateSnapshot = () => {
        const defaultName = `snap-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}`;
        setSnapshotNameInput(defaultName);
        setIsSnapshotDialogOpen(true);
    };

    const handleConfirmCreateSnapshot = async () => {
        if (!snapshotNameInput.trim()) return;
        setIsActionLoading('snapshot');
        try {
            await createSnapshot(snapshotNameInput.trim());
            setIsSnapshotDialogOpen(false);
            await loadData(true);
        } catch (err: any) {
            setError(err?.message || t('disks.snapshots.error_create', 'Failed to create snapshot.'));
        } finally {
            setIsActionLoading(null);
        }
    };

    const handleDeleteSnapshot = (name: string) => {
        setConfirmModal({
            isOpen: true,
            title: t('disks.snapshots.delete_title', 'Delete Snapshot'),
            message: t('disks.snapshots.delete_confirm', 'Are you sure you want to permanently delete snapshot "{{name}}"? This action cannot be undone.', {
                name
            }),
            confirmText: t('disks.snapshots.delete', 'Delete'),
            variant: 'danger',
            onConfirm: async () => {
                setConfirmModal(prev => ({ ...prev, isLoading: true }));
                try {
                    await deleteSnapshot(name);
                    await loadData(true);
                } finally {
                    setConfirmModal(prev => ({ ...prev, isOpen: false, isLoading: false }));
                }
            }
        });
    };

    const handleRollbackSnapshot = (name: string) => {
        setConfirmModal({
            isOpen: true,
            title: t('disks.snapshots.rollback_title', 'Rollback Snapshot'),
            message: t(
                'disks.snapshots.rollback_confirm',
                'Are you sure you want to rollback to snapshot "{{name}}"? Any changes made to files since this snapshot was created will be discarded.',
                { name }
            ),
            confirmText: t('disks.snapshots.rollback', 'Rollback'),
            variant: 'warning',
            onConfirm: async () => {
                setConfirmModal(prev => ({ ...prev, isLoading: true }));
                try {
                    await rollbackSnapshot(name);
                    await loadData(true);
                } finally {
                    setConfirmModal(prev => ({ ...prev, isOpen: false, isLoading: false }));
                }
            }
        });
    };

    const handleCreatePool = async (payload: CreatePoolPayload) => {
        setConfirmModal({
            isOpen: true,
            title: t('disks.create.confirm_title', 'Create Disk Array'),
            message: t(
                'disks.create.confirm_message',
                'Creating a new array will format the selected disks ({{count}} selected). All existing data on those disks will be permanently erased. Do you wish to proceed?',
                { count: payload.disks.length }
            ),
            confirmText: t('disks.create.submit', 'Create Array'),
            variant: 'danger',
            onConfirm: async () => {
                setConfirmModal(prev => ({ ...prev, isLoading: true }));
                try {
                    await createPool(payload);
                    await loadData(true);
                } catch (err: any) {
                    setError(err?.message || t('disks.create.error', 'Failed to create disk array.'));
                } finally {
                    setConfirmModal(prev => ({ ...prev, isOpen: false, isLoading: false }));
                }
            }
        });
    };

    const handleAddDisk = async (diskPath: string) => {
        setConfirmModal({
            isOpen: true,
            title: t('disks.add.confirm_title', 'Add Disk to Array'),
            message: t(
                'disks.add.confirm_message',
                'Disk {{path}} will be formatted and added to expand the active array. This operation can take a significant amount of time. Proceed?',
                { path: diskPath }
            ),
            confirmText: t('disks.add.submit', 'Add Disk to Array'),
            variant: 'warning',
            onConfirm: async () => {
                setConfirmModal(prev => ({ ...prev, isLoading: true }));
                try {
                    await expandPool(diskPath);
                    await loadData(true);
                } catch (err: any) {
                    setError(err?.message || t('disks.add.error', 'Failed to expand disk array.'));
                } finally {
                    setConfirmModal(prev => ({ ...prev, isOpen: false, isLoading: false }));
                }
            }
        });
    };

    const handleFormatDisk = (disk: DiskItem) => {
        const path = disk.path || (disk.name ? `/dev/${disk.name}` : '');
        setConfirmModal({
            isOpen: true,
            title: t('disks.format_modal.title', 'Format Disk'),
            message: t('disks.format_modal.confirm', 'Are you sure you want to format {{path}}? All partitions and data on this drive will be wiped.', {
                path
            }),
            confirmText: t('disks.format', 'Format'),
            variant: 'danger',
            onConfirm: async () => {
                setConfirmModal(prev => ({ ...prev, isLoading: true }));
                try {
                    await formatDisk(path);
                    await loadData(true);
                } catch (err: any) {
                    setError(err?.message || t('disks.format_modal.error', 'Failed to format disk.'));
                } finally {
                    setConfirmModal(prev => ({ ...prev, isOpen: false, isLoading: false }));
                }
            }
        });
    };

    // Calculate capacity percentages
    const usedBytes = pool?.capacity?.used ?? 0;
    const totalBytes = pool?.capacity?.total ?? 0;
    const capacityPercent = formatPercent(usedBytes, totalBytes);

    return (
        <div className="space-y-6">
            {/* Top Navigation & Breadcrumb Banner */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-gray-100 dark:border-zinc-800">
                <div className="flex items-center gap-3">
                    <button
                        type="button"
                        onClick={() => onNavigate?.('dashboard')}
                        className="p-2 rounded-xl bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 text-gray-600 dark:text-zinc-300 hover:bg-gray-50 dark:hover:bg-zinc-700 shadow-xs cursor-pointer transition-colors"
                        title={t('common.back_to_dashboard', 'Back to Dashboard')}
                    >
                        <ArrowLeft className="w-4 h-4" />
                    </button>
                    <div>
                        <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-zinc-400">
                            <button
                                onClick={() => onNavigate?.('dashboard')}
                                className="hover:text-indigo-600 dark:hover:text-indigo-400 cursor-pointer"
                            >
                                {t('nav.dashboard', 'Dashboard')}
                            </button>
                            <span>/</span>
                            <span className="text-gray-900 dark:text-white font-medium">
                                {t('nav.disks', 'Disk Management')}
                            </span>
                        </div>
                        <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mt-0.5">
                            {t('disks.page_title', 'Disk Management')}
                        </h2>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <button
                        type="button"
                        onClick={() => loadData(true)}
                        disabled={refreshing}
                        className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl bg-white dark:bg-zinc-800 text-gray-700 dark:text-zinc-200 border border-gray-200 dark:border-zinc-700 hover:bg-gray-50 dark:hover:bg-zinc-700 shadow-xs transition-all cursor-pointer"
                    >
                        <RotateCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-indigo-500' : ''}`} />
                        <span>{refreshing ? t('dashboard.refreshing', 'Refreshing...') : t('dashboard.refresh', 'Refresh')}</span>
                    </button>
                </div>
            </div>

            {error && (
                <div className="p-4 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 text-red-600 dark:text-red-400 text-xs flex items-center justify-between">
                    <span>{error}</span>
                    <button onClick={() => setError(null)} className="font-semibold cursor-pointer">
                        ✕
                    </button>
                </div>
            )}

            {/* Array Overview Banner (if configured) */}
            {pool && pool.isConfigured && (
                <div className="p-6 rounded-2xl bg-gradient-to-r from-indigo-500/10 via-purple-500/5 to-transparent border border-indigo-500/20 dark:border-indigo-500/30">
                    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                        <div className="space-y-2">
                            <div className="flex items-center gap-3">
                                <div className="p-2.5 rounded-xl bg-indigo-600 dark:bg-indigo-500 text-white shadow-md shadow-indigo-600/20">
                                    <Database className="w-5 h-5" />
                                </div>
                                <div>
                                    <div className="flex items-center gap-2">
                                        <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                                            {t('disks.array_title', 'Disk Array')}
                                        </h3>
                                        <span
                                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                                                pool.isMounted
                                                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/50'
                                                    : 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 border border-amber-200 dark:border-amber-800/50'
                                            }`}
                                        >
                                            {pool.isMounted
                                                ? t('disks.status.mounted', 'Mounted & Accessible')
                                                : t('disks.status.unmounted', 'Unmounted')}
                                        </span>
                                    </div>
                                    <p className="text-xs text-gray-500 dark:text-zinc-400">
                                        {disks.filter(d => d.inPool).length} {t('disks.active_disks', 'drives active in array')}
                                    </p>
                                </div>
                            </div>

                            {/* Features badges */}
                            <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/80 dark:bg-zinc-800/80 border border-gray-200/80 dark:border-zinc-700 text-gray-700 dark:text-zinc-300">
                                    <Shield className="w-3.5 h-3.5 text-emerald-500" />
                                    <span>{pool.settings?.redundancy ? t('disks.settings.redundancy', 'Redundancy') : t('disks.settings.standard', 'Standard')}</span>
                                </span>
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/80 dark:bg-zinc-800/80 border border-gray-200/80 dark:border-zinc-700 text-gray-700 dark:text-zinc-300">
                                    <Archive className="w-3.5 h-3.5 text-sky-500" />
                                    <span>{pool.settings?.compression ? t('disks.settings.compressed', 'Compression') : t('disks.settings.uncompressed', 'Uncompressed')}</span>
                                </span>
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/80 dark:bg-zinc-800/80 border border-gray-200/80 dark:border-zinc-700 text-gray-700 dark:text-zinc-300">
                                    <Lock className="w-3.5 h-3.5 text-amber-500" />
                                    <span>{pool.settings?.encryption ? t('disks.settings.encrypted', 'Encryption') : t('disks.settings.unencrypted', 'Unencrypted')}</span>
                                </span>
                            </div>
                        </div>

                        {/* Capacity meter */}
                        {totalBytes > 0 && (
                            <div className="lg:w-80 p-4 rounded-xl bg-white dark:bg-zinc-900/80 border border-gray-100 dark:border-zinc-800 shadow-xs">
                                <div className="flex justify-between items-center text-xs mb-1.5">
                                    <span className="font-semibold text-gray-700 dark:text-zinc-300">
                                        {t('disks.capacity_usage', 'Array Capacity')}
                                    </span>
                                    <span className="font-bold text-gray-900 dark:text-white">
                                        {capacityPercent}%
                                    </span>
                                </div>
                                <div className="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-2.5 overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all duration-500 ${
                                            capacityPercent > 85 ? 'bg-red-500' : 'bg-indigo-600 dark:bg-indigo-500'
                                        }`}
                                        style={{ width: `${Math.min(100, capacityPercent)}%` }}
                                    />
                                </div>
                                <div className="flex justify-between text-[11px] font-mono text-gray-500 dark:text-zinc-400 mt-2">
                                    <span>{t('disks.used', 'Used')}: {formatBytes(usedBytes)}</span>
                                    <span>{t('disks.total', 'Total')}: {formatBytes(totalBytes)}</span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Section 1: Physical Disks Grid */}
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <HardDrive className="w-4 h-4 text-indigo-500" />
                        <h3 className="text-base font-bold text-gray-900 dark:text-white">
                            {t('disks.physical_disks_title', 'Physical Disks')}
                        </h3>
                    </div>
                    <span className="text-xs text-gray-500 dark:text-zinc-400">
                        {disks.length} {t('disks.detected_count', 'detected drives')}
                    </span>
                </div>

                {loading && disks.length === 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
                        {[1, 2, 3, 4].map(i => (
                            <div key={i} className="h-48 rounded-2xl bg-gray-200 dark:bg-zinc-800/60" />
                        ))}
                    </div>
                ) : disks.length === 0 ? (
                    <div className="p-8 rounded-2xl bg-white dark:bg-zinc-900 border border-gray-100 dark:border-zinc-800 text-center text-xs text-gray-500 dark:text-zinc-400">
                        <HardDrive className="w-8 h-8 mx-auto mb-2 opacity-40 text-gray-400" />
                        <p>{t('disks.no_disks_found', 'No storage drives were detected on this system.')}</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {disks.map((d, index) => (
                            <DiskCard
                                key={d.path || d.name || index}
                                disk={d}
                                index={index}
                                onCheckHealth={disk => setSelectedSmartDisk(disk)}
                                onFormat={disk => handleFormatDisk(disk)}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* Section 2: Pool Tools & Operations */}
            <div className="space-y-4 pt-2">
                {pool?.isConfigured ? (
                    <>
                        <DiskToolsCard
                            isMounted={!!pool.isMounted}
                            scrubInfo={scrubInfo}
                            onVerify={handleVerify}
                            onToggleMount={handleToggleMount}
                            actionLoading={isActionLoading}
                        />

                        {attachableDisks.length > 0 && (
                            <AddDisksCard
                                attachableDisks={attachableDisks}
                                onAddDisk={handleAddDisk}
                            />
                        )}

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <SnapshotsCard
                                snapshots={snapshots}
                                onRollback={handleRollbackSnapshot}
                                onDelete={handleDeleteSnapshot}
                                onCreateSnapshot={handleOpenCreateSnapshot}
                            />

                            {scrubReport && <ScrubReportCard report={scrubReport} />}
                        </div>
                    </>
                ) : (
                    <>
                        {/* Pool Not Configured Warning */}
                        <div className="p-6 rounded-2xl bg-amber-50/60 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50">
                            <div className="flex items-center gap-3 text-amber-800 dark:text-amber-300">
                                <AlertTriangle className="w-5 h-5 shrink-0 text-amber-600 dark:text-amber-400" />
                                <div>
                                    <h4 className="text-sm font-semibold">
                                        {t('disks.no_pool_title', 'No Storage Array Configured')}
                                    </h4>
                                    <p className="text-xs text-amber-700 dark:text-amber-300/90 mt-0.5">
                                        {t(
                                            'disks.no_pool_desc',
                                            'Create a new disk array using your installed drives below, or import an existing array.'
                                        )}
                                    </p>
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <CreateArrayCard
                                availableDisks={disks}
                                onCreatePool={handleCreatePool}
                            />

                            {importablePools.map((p, idx) => (
                                <ImportArrayCard
                                    key={p.name || idx}
                                    pool={p}
                                    onImport={(pName) => console.log('Importing pool', pName)}
                                />
                            ))}
                        </div>
                    </>
                )}
            </div>

            {/* SMART Diagnostics Dialog */}
            <SmartModal
                disk={selectedSmartDisk}
                isOpen={selectedSmartDisk !== null}
                onClose={() => setSelectedSmartDisk(null)}
            />

            {/* Confirmation Dialog */}
            <ConfirmModal
                isOpen={confirmModal.isOpen}
                title={confirmModal.title}
                message={confirmModal.message}
                confirmText={confirmModal.confirmText}
                confirmVariant={confirmModal.variant}
                isLoading={confirmModal.isLoading}
                onConfirm={confirmModal.onConfirm}
                onCancel={() => setConfirmModal(prev => ({ ...prev, isOpen: false }))}
            />

            {/* Create Snapshot Dialog */}
            {isSnapshotDialogOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
                    <div className="bg-white dark:bg-zinc-900 rounded-2xl w-full max-w-md p-6 shadow-2xl ring-1 ring-gray-900/10 dark:ring-white/10 space-y-4">
                        <h3 className="text-base font-bold text-gray-900 dark:text-white">
                            {t('disks.snapshots.create_dialog_title', 'Create New Snapshot')}
                        </h3>
                        <p className="text-xs text-gray-500 dark:text-zinc-400">
                            {t('disks.snapshots.create_dialog_desc', 'Enter an identifier name for the point-in-time recovery image:')}
                        </p>
                        <input
                            type="text"
                            value={snapshotNameInput}
                            onChange={e => setSnapshotNameInput(e.target.value)}
                            className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white font-mono text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                            placeholder="e.g. backup-2026-11-08"
                        />
                        <div className="flex justify-end gap-2 pt-2">
                            <button
                                type="button"
                                onClick={() => setIsSnapshotDialogOpen(false)}
                                className="px-4 py-2 text-xs font-semibold rounded-xl bg-gray-100 dark:bg-zinc-800 text-gray-700 dark:text-zinc-300 hover:bg-gray-200 dark:hover:bg-zinc-700 cursor-pointer transition-colors"
                            >
                                {t('common.cancel', 'Cancel')}
                            </button>
                            <button
                                type="button"
                                onClick={handleConfirmCreateSnapshot}
                                disabled={!snapshotNameInput.trim() || isActionLoading === 'snapshot'}
                                className="px-4 py-2 text-xs font-semibold rounded-xl bg-purple-600 text-white hover:bg-purple-500 shadow-xs cursor-pointer transition-colors disabled:opacity-50"
                            >
                                {isActionLoading === 'snapshot' ? t('common.saving', 'Creating...') : t('disks.tools.create_snapshot', 'Create')}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
