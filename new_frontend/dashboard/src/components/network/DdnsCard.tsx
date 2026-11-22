import { useState } from 'react';
import { Globe, Plus, Trash2, Edit3, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { DdnsProviderItem } from '../../types/network';

interface DdnsCardProps {
    providers: DdnsProviderItem[];
    protocols: string[];
    onAddProvider: (payload: {
        name: string;
        proto: string;
        server?: string;
        username?: string;
        password?: string;
        hostname?: string;
    }) => Promise<void>;
    onEditProvider: (payload: {
        name: string;
        enabled: boolean;
        proto: string;
        server?: string;
        username?: string;
        password?: string;
        hostname?: string;
    }) => Promise<void>;
    onDeleteProvider: (name: string) => Promise<void>;
}

export default function DdnsCard({
    providers,
    protocols,
    onAddProvider,
    onEditProvider,
    onDeleteProvider
}: DdnsCardProps) {
    const { t } = useTranslation();

    const [isAddOpen, setIsAddOpen] = useState(false);
    const [editingProviderName, setEditingProviderName] = useState<string | null>(null);

    // Add Form State
    const [addName, setAddName] = useState('');
    const [addProto, setAddProto] = useState(protocols[0] || 'duckdns');
    const [addHostname, setAddHostname] = useState('');
    const [addServer, setAddServer] = useState('');
    const [addUsername, setAddUsername] = useState('');
    const [addPassword, setAddPassword] = useState('');
    const [isSubmittingAdd, setIsSubmittingAdd] = useState(false);

    // Edit Form State
    const [editEnabled, setEditEnabled] = useState(true);
    const [editProto, setEditProto] = useState('');
    const [editHostname, setEditHostname] = useState('');
    const [editServer, setEditServer] = useState('');
    const [editUsername, setEditUsername] = useState('');
    const [editPassword, setEditPassword] = useState('');
    const [isSubmittingEdit, setIsSubmittingEdit] = useState(false);

    const startEditing = (p: DdnsProviderItem) => {
        setEditingProviderName(p.name);
        setEditEnabled(p.enabled);
        setEditProto(p.protocol);
        setEditHostname(p.hostname || '');
        setEditServer(p.server || '');
        setEditUsername(p.username || '');
        setEditPassword(p.password || '');
    };

    const handleAddSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!addName.trim() || !addProto.trim()) return;
        setIsSubmittingAdd(true);
        try {
            await onAddProvider({
                name: addName.trim(),
                proto: addProto.trim(),
                hostname: addHostname.trim() || undefined,
                server: addServer.trim() || undefined,
                username: addUsername.trim() || undefined,
                password: addPassword.trim() || undefined
            });
            setAddName('');
            setAddHostname('');
            setAddServer('');
            setAddUsername('');
            setAddPassword('');
            setIsAddOpen(false);
        } finally {
            setIsSubmittingAdd(false);
        }
    };

    const handleEditSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!editingProviderName) return;
        setIsSubmittingEdit(true);
        try {
            await onEditProvider({
                name: editingProviderName,
                enabled: editEnabled,
                proto: editProto,
                hostname: editHostname.trim() || undefined,
                server: editServer.trim() || undefined,
                username: editUsername.trim() || undefined,
                password: editPassword.trim() || undefined
            });
            setEditingProviderName(null);
        } finally {
            setIsSubmittingEdit(false);
        }
    };

    const handleToggleQuick = async (p: DdnsProviderItem) => {
        await onEditProvider({
            name: p.name,
            enabled: !p.enabled,
            proto: p.protocol,
            hostname: p.hostname,
            server: p.server,
            username: p.username,
            password: p.password
        });
    };

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 transition-all hover:shadow-md space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between gap-4 sm:gap-6 pb-4 border-b border-gray-100 dark:border-zinc-800">
                <div className="flex items-center gap-3 min-w-0">
                    <div className="p-2.5 rounded-xl bg-sky-50 dark:bg-sky-950/40 text-sky-600 dark:text-sky-400 shrink-0">
                        <Globe className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                        <h3 className="text-base font-bold text-gray-900 dark:text-white">
                            {t('network_page.ddns_title', 'Dynamic DNS (DDNS)')}
                        </h3>
                        <p className="text-xs text-gray-500 dark:text-zinc-400 mt-0.5">
                            {t('network_page.ddns_subtitle', 'Keep public domains synchronized with your network IP')}
                        </p>
                    </div>
                </div>

                <button
                    type="button"
                    onClick={() => setIsAddOpen(!isAddOpen)}
                    className="shrink-0 whitespace-nowrap inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-xl bg-sky-600 text-white hover:bg-sky-500 shadow-sm transition-all cursor-pointer"
                >
                    <Plus className="w-3.5 h-3.5" />
                    <span>{t('network_page.add_ddns', 'Add Provider')}</span>
                </button>
            </div>

            {/* Add Provider Accordion Form */}
            {isAddOpen && (
                <form onSubmit={handleAddSubmit} className="p-4 rounded-xl bg-sky-50/50 dark:bg-sky-950/20 border border-sky-100 dark:border-sky-900/30 space-y-4 text-xs animate-in fade-in duration-150">
                    <div className="flex items-center justify-between pb-2 border-b border-sky-200/50 dark:border-sky-900/40">
                        <span className="font-bold text-sky-900 dark:text-sky-200">
                            {t('network_page.add_ddns', 'Add Dynamic DNS Provider')}
                        </span>
                        <button
                            type="button"
                            onClick={() => setIsAddOpen(false)}
                            className="p-1 rounded text-sky-600 dark:text-sky-400 hover:bg-sky-100 dark:hover:bg-sky-900/40 cursor-pointer"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-[11px] font-medium text-gray-700 dark:text-zinc-300 mb-1">
                                {t('widgets.disks.name', 'Provider Name')} *
                            </label>
                            <input
                                type="text"
                                required
                                value={addName}
                                onChange={e => setAddName(e.target.value)}
                                placeholder="e.g. duckdns-home"
                                className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs focus:ring-2 focus:ring-sky-500 focus:outline-none"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-medium text-gray-700 dark:text-zinc-300 mb-1">
                                {t('network_page.protocol', 'Protocol')} *
                            </label>
                            <select
                                value={addProto}
                                onChange={e => setAddProto(e.target.value)}
                                className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs focus:ring-2 focus:ring-sky-500 focus:outline-none cursor-pointer"
                            >
                                {protocols.map(p => (
                                    <option key={p} value={p}>{p}</option>
                                ))}
                            </select>
                        </div>

                        <div>
                            <label className="block text-[11px] font-medium text-gray-700 dark:text-zinc-300 mb-1">
                                {t('network_page.hostname', 'Domain Hostname')}
                            </label>
                            <input
                                type="text"
                                value={addHostname}
                                onChange={e => setAddHostname(e.target.value)}
                                placeholder="myhome.duckdns.org"
                                className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs focus:ring-2 focus:ring-sky-500 focus:outline-none"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-medium text-gray-700 dark:text-zinc-300 mb-1">
                                {t('network_page.server', 'Server (optional)')}
                            </label>
                            <input
                                type="text"
                                value={addServer}
                                onChange={e => setAddServer(e.target.value)}
                                placeholder="www.duckdns.org"
                                className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs focus:ring-2 focus:ring-sky-500 focus:outline-none"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-medium text-gray-700 dark:text-zinc-300 mb-1">
                                {t('network_page.username', 'Username / Token')}
                            </label>
                            <input
                                type="text"
                                value={addUsername}
                                onChange={e => setAddUsername(e.target.value)}
                                className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs focus:ring-2 focus:ring-sky-500 focus:outline-none"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] font-medium text-gray-700 dark:text-zinc-300 mb-1">
                                {t('network_page.password', 'Password / Key')}
                            </label>
                            <input
                                type="password"
                                value={addPassword}
                                onChange={e => setAddPassword(e.target.value)}
                                className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs focus:ring-2 focus:ring-sky-500 focus:outline-none"
                            />
                        </div>
                    </div>

                    <div className="flex justify-end gap-2 pt-1">
                        <button
                            type="button"
                            onClick={() => setIsAddOpen(false)}
                            className="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-zinc-700 text-gray-700 dark:text-zinc-300 bg-white dark:bg-zinc-800 hover:bg-gray-50 cursor-pointer font-medium"
                        >
                            {t('common.cancel', 'Cancel')}
                        </button>
                        <button
                            type="submit"
                            disabled={isSubmittingAdd || !addName.trim()}
                            className="px-4 py-1.5 rounded-xl font-semibold text-white bg-sky-600 hover:bg-sky-500 shadow-sm cursor-pointer disabled:opacity-50"
                        >
                            {isSubmittingAdd ? t('common.saving', 'Saving...') : t('network_page.submit_add', 'Add Provider')}
                        </button>
                    </div>
                </form>
            )}

            {/* Providers List */}
            {providers.length === 0 ? (
                <div className="p-8 rounded-xl border border-dashed border-gray-200 dark:border-zinc-800 text-center text-xs text-gray-400 dark:text-zinc-500">
                    {t('network_page.no_ddns', 'No dynamic DNS providers configured.')}
                </div>
            ) : (
                <div className="space-y-3">
                    {providers.map(p => {
                        const isEditingThis = editingProviderName === p.name;
                        return (
                            <div key={p.name} className="border border-gray-100 dark:border-zinc-800 rounded-xl overflow-hidden transition-all">
                                <div className="flex items-center justify-between p-4 bg-gray-50/40 dark:bg-zinc-800/30">
                                    <div className="flex items-center gap-3">
                                        <button
                                            type="button"
                                            onClick={() => handleToggleQuick(p)}
                                            className={`w-3.5 h-3.5 rounded-full transition-colors cursor-pointer ${
                                                p.enabled ? 'bg-emerald-500 ring-2 ring-emerald-500/20' : 'bg-zinc-400'
                                            }`}
                                            title={p.enabled ? t('network_page.status_enabled', 'Active') : t('network_page.status_disabled', 'Inactive')}
                                        />
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="font-bold text-gray-900 dark:text-white text-xs">
                                                    {p.name}
                                                </span>
                                                <span className="text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-gray-100 dark:bg-zinc-800 text-gray-600 dark:text-zinc-400">
                                                    {p.protocol}
                                                </span>
                                            </div>
                                            {p.hostname && (
                                                <p className="text-[11px] font-mono text-gray-500 dark:text-zinc-400 mt-0.5">
                                                    {p.hostname}
                                                </p>
                                            )}
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-1.5">
                                        <button
                                            type="button"
                                            onClick={() => isEditingThis ? setEditingProviderName(null) : startEditing(p)}
                                            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 dark:hover:text-zinc-200 hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                                            title={t('network_page.edit_ddns', 'Edit DDNS')}
                                        >
                                            <Edit3 className="w-3.5 h-3.5" />
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => onDeleteProvider(p.name)}
                                            className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors cursor-pointer"
                                            title={t('network_page.delete_ddns', 'Delete')}
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                </div>

                                {/* Edit Accordion Drawer */}
                                {isEditingThis && (
                                    <form onSubmit={handleEditSubmit} className="p-4 bg-white dark:bg-zinc-900 border-t border-gray-100 dark:border-zinc-800 space-y-3 text-xs animate-in fade-in duration-100">
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                            <div className="sm:col-span-2 flex items-center justify-between p-2 rounded-lg bg-gray-50 dark:bg-zinc-800/40">
                                                <span className="font-medium text-gray-800 dark:text-zinc-200">
                                                    {t('widgets.access.active_count', 'Enable Provider')}
                                                </span>
                                                <label className="relative inline-flex items-center cursor-pointer">
                                                    <input
                                                        type="checkbox"
                                                        checked={editEnabled}
                                                        onChange={e => setEditEnabled(e.target.checked)}
                                                        className="sr-only peer"
                                                    />
                                                    <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-sky-600" />
                                                </label>
                                            </div>

                                            <div>
                                                <label className="block text-[11px] font-medium text-gray-700 dark:text-zinc-300 mb-1">
                                                    {t('network_page.protocol', 'Protocol')}
                                                </label>
                                                <select
                                                    value={editProto}
                                                    onChange={e => setEditProto(e.target.value)}
                                                    className="w-full px-3 py-1.5 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs cursor-pointer"
                                                >
                                                    {protocols.map(pr => (
                                                        <option key={pr} value={pr}>{pr}</option>
                                                    ))}
                                                </select>
                                            </div>

                                            <div>
                                                <label className="block text-[11px] font-medium text-gray-700 dark:text-zinc-300 mb-1">
                                                    {t('network_page.hostname', 'Domain Hostname')}
                                                </label>
                                                <input
                                                    type="text"
                                                    value={editHostname}
                                                    onChange={e => setEditHostname(e.target.value)}
                                                    className="w-full px-3 py-1.5 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs"
                                                />
                                            </div>

                                            <div>
                                                <label className="block text-[11px] font-medium text-gray-700 dark:text-zinc-300 mb-1">
                                                    {t('network_page.username', 'Username / Token')}
                                                </label>
                                                <input
                                                    type="text"
                                                    value={editUsername}
                                                    onChange={e => setEditUsername(e.target.value)}
                                                    className="w-full px-3 py-1.5 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs"
                                                />
                                            </div>

                                            <div>
                                                <label className="block text-[11px] font-medium text-gray-700 dark:text-zinc-300 mb-1">
                                                    {t('network_page.password', 'Password / Key')}
                                                </label>
                                                <input
                                                    type="password"
                                                    value={editPassword}
                                                    onChange={e => setEditPassword(e.target.value)}
                                                    className="w-full px-3 py-1.5 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs"
                                                />
                                            </div>
                                        </div>

                                        <div className="flex justify-end gap-2 pt-1">
                                            <button
                                                type="button"
                                                onClick={() => setEditingProviderName(null)}
                                                className="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-zinc-700 text-gray-700 dark:text-zinc-300 hover:bg-gray-50 cursor-pointer"
                                            >
                                                {t('common.cancel', 'Cancel')}
                                            </button>
                                            <button
                                                type="submit"
                                                disabled={isSubmittingEdit}
                                                className="px-3 py-1.5 rounded-lg font-semibold text-white bg-sky-600 hover:bg-sky-500 shadow-xs cursor-pointer disabled:opacity-50"
                                            >
                                                {isSubmittingEdit ? t('common.saving', 'Saving...') : t('network_page.submit_save', 'Save Changes')}
                                            </button>
                                        </div>
                                    </form>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
