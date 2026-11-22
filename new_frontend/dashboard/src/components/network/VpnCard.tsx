import { useState, useEffect } from 'react';
import {
    Shield,
    Key,
    Copy,
    Check,
    Download,
    RotateCw,
    Plus,
    Trash2,
    Laptop,
    HelpCircle,
    ChevronDown,
    ChevronUp,
    Power
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { NetworkInterfaceItem } from '../../types/dashboard';
import type { VpnPeerItem } from '../../types/network';

interface VpnCardProps {
    vpnIface: NetworkInterfaceItem | null;
    endpoint: string | null;
    publicKey: string | null;
    peers: VpnPeerItem[];
    onToggleVpn: (action: 'up' | 'down') => Promise<void>;
    onSaveConfig: (cfg: { address: string; netmask: string; endpoint: string }) => Promise<void>;
    onGenKeys: () => Promise<void>;
    onAddPeer: (name: string, publicKey: string) => Promise<void>;
    onDeletePeer: (name: string) => Promise<void>;
    isLoading?: boolean;
}

export default function VpnCard({
    vpnIface,
    endpoint,
    publicKey,
    peers,
    onToggleVpn,
    onSaveConfig,
    onGenKeys,
    onAddPeer,
    onDeletePeer,
    isLoading = false
}: VpnCardProps) {
    const { t } = useTranslation();

    const isEnabled = vpnIface?.enabled ?? false;

    // Server Config form state
    const [address, setAddress] = useState(vpnIface?.ipv4?.address || '10.8.0.1');
    const [netmask, setNetmask] = useState(vpnIface?.ipv4?.netmask || '255.255.255.0');
    const [publicEndpoint, setPublicEndpoint] = useState(endpoint || '');

    // Add peer form state
    const [newPeerName, setNewPeerName] = useState('');
    const [newPeerPubKey, setNewPeerPubKey] = useState('');

    // UI state
    const [copiedKey, setCopiedKey] = useState(false);
    const [copiedTemplate, setCopiedTemplate] = useState(false);
    const [showGuide, setShowGuide] = useState(false);
    const [savingConfig, setSavingConfig] = useState(false);
    const [addingPeer, setAddingPeer] = useState(false);

    useEffect(() => {
        if (vpnIface?.ipv4?.address) setAddress(vpnIface.ipv4.address);
        if (vpnIface?.ipv4?.netmask) setNetmask(vpnIface.ipv4.netmask);
        if (endpoint) setPublicEndpoint(endpoint);
    }, [vpnIface, endpoint]);

    const handleCopyPublicKey = () => {
        if (!publicKey) return;
        navigator.clipboard.writeText(publicKey);
        setCopiedKey(true);
        setTimeout(() => setCopiedKey(false), 2000);
    };

    const handleDownloadKey = () => {
        if (!publicKey) return;
        const blob = new Blob([publicKey], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'wireguard-server.key';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const handleSaveConfig = async (e: React.FormEvent) => {
        e.preventDefault();
        setSavingConfig(true);
        try {
            await onSaveConfig({
                address: address.trim(),
                netmask: netmask.trim(),
                endpoint: publicEndpoint.trim()
            });
        } finally {
            setSavingConfig(false);
        }
    };

    const handleAddPeerSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newPeerName.trim() || !newPeerPubKey.trim()) return;
        setAddingPeer(true);
        try {
            await onAddPeer(newPeerName.trim(), newPeerPubKey.trim());
            setNewPeerName('');
            setNewPeerPubKey('');
        } finally {
            setAddingPeer(false);
        }
    };

    const clientTemplate = `[Interface]
PrivateKey = YOUR_CLIENT_PRIVATE_KEY
Address = 10.8.0.2/24
DNS = 1.1.1.1

[Peer]
PublicKey = ${publicKey || 'SERVER_PUBLIC_KEY'}
Endpoint = ${publicEndpoint || 'YOUR_NAS_PUBLIC_IP'}:51820
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25`;

    const handleCopyTemplate = () => {
        navigator.clipboard.writeText(clientTemplate);
        setCopiedTemplate(true);
        setTimeout(() => setCopiedTemplate(false), 2000);
    };

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 transition-all hover:shadow-md space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400">
                        <Shield className="w-5 h-5" />
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <h3 className="text-base font-bold text-gray-900 dark:text-white">
                                {t('network_page.vpn_title', 'WireGuard VPN')}
                            </h3>
                            <span className="text-xs px-2 py-0.5 rounded-md font-mono bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400 font-semibold">
                                WireGuard
                            </span>
                        </div>
                        <p className="text-xs text-gray-500 dark:text-zinc-400 mt-0.5">
                            {t('network_page.vpn_subtitle', 'Encrypted remote access tunnel into your private network')}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
                        isEnabled
                            ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/50'
                            : 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-700'
                    }`}>
                        <span className={`w-2 h-2 rounded-full ${isEnabled ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-400'}`} />
                        {isEnabled
                            ? t('network_page.status_up', 'Active')
                            : t('network_page.status_down', 'Disabled')}
                    </span>

                    <button
                        type="button"
                        onClick={() => onToggleVpn(isEnabled ? 'down' : 'up')}
                        disabled={isLoading}
                        title={isEnabled ? t('network_page.disable_iface', 'Disconnect') : t('network_page.enable_iface', 'Connect')}
                        className={`p-2 rounded-xl border transition-all cursor-pointer ${
                            isEnabled
                                ? 'bg-red-50 hover:bg-red-100 border-red-200 text-red-600 dark:bg-red-950/40 dark:hover:bg-red-950/60 dark:border-red-900/50 dark:text-red-400'
                                : 'bg-emerald-50 hover:bg-emerald-100 border-emerald-200 text-emerald-600 dark:bg-emerald-950/40 dark:hover:bg-emerald-950/60 dark:border-emerald-900/50 dark:text-emerald-400'
                        } disabled:opacity-50`}
                    >
                        <Power className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Server Settings Form */}
            <form onSubmit={handleSaveConfig} className="space-y-4">
                <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-zinc-400">
                        {t('network_page.vpn_settings', 'VPN Configuration')}
                    </h4>
                </div>

                <div className="space-y-3 text-xs">
                    <div>
                        <label className="block text-xs font-medium text-gray-700 dark:text-zinc-300 mb-1">
                            {t('network_page.vpn_address', 'Internal VPN IP')}
                        </label>
                        <input
                            type="text"
                            value={address}
                            onChange={e => setAddress(e.target.value)}
                            className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white font-mono text-xs focus:ring-2 focus:ring-purple-500 focus:outline-none"
                            placeholder="10.8.0.1"
                        />
                    </div>
                    <div>
                        <label className="block text-xs font-medium text-gray-700 dark:text-zinc-300 mb-1">
                            {t('network_page.vpn_netmask', 'Subnet Mask')}
                        </label>
                        <input
                            type="text"
                            value={netmask}
                            onChange={e => setNetmask(e.target.value)}
                            className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white font-mono text-xs focus:ring-2 focus:ring-purple-500 focus:outline-none"
                            placeholder="255.255.255.0"
                        />
                    </div>
                    <div>
                        <label className="block text-xs font-medium text-gray-700 dark:text-zinc-300 mb-1">
                            {t('network_page.vpn_endpoint', 'Public Endpoint (IP or Hostname)')}
                        </label>
                        <input
                            type="text"
                            value={publicEndpoint}
                            onChange={e => setPublicEndpoint(e.target.value)}
                            className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white font-mono text-xs focus:ring-2 focus:ring-purple-500 focus:outline-none"
                            placeholder="e.g. 1.2.3.4 or myhome.ddns.net"
                        />
                    </div>
                </div>

                <div className="flex justify-end">
                    <button
                        type="submit"
                        disabled={savingConfig || isLoading}
                        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl font-semibold text-xs text-white bg-purple-600 hover:bg-purple-500 shadow-sm transition-all cursor-pointer disabled:opacity-50"
                    >
                        {savingConfig ? (
                            <RotateCw className="w-3.5 h-3.5 animate-spin" />
                        ) : null}
                        <span>{t('network_page.save_vpn_config', 'Save VPN Settings')}</span>
                    </button>
                </div>
            </form>

            {/* Public Key & Security */}
            <div className="p-4 rounded-xl bg-purple-50/50 dark:bg-purple-950/20 border border-purple-100 dark:border-purple-900/30 space-y-3 text-xs">
                <div className="flex items-center justify-between">
                    <span className="font-semibold text-gray-900 dark:text-zinc-100 flex items-center gap-2">
                        <Key className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                        {t('network_page.pubkey', 'Server Public Key')}
                    </span>
                    <button
                        type="button"
                        onClick={onGenKeys}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 hover:bg-amber-100 cursor-pointer transition-colors"
                    >
                        <RotateCw className="w-3 h-3" />
                        <span>{t('network_page.gen_keys', 'Regenerate Keys')}</span>
                    </button>
                </div>

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                    <input
                        type="text"
                        readOnly
                        value={publicKey || t('widgets.disks.unknown', 'Unknown')}
                        className="flex-1 px-3 py-2 rounded-lg bg-white dark:bg-zinc-800 border border-purple-200 dark:border-purple-900/50 font-mono text-[11px] text-gray-800 dark:text-zinc-200 select-all"
                    />
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={handleCopyPublicKey}
                            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white dark:bg-zinc-800 border border-purple-200 dark:border-purple-900/50 text-gray-700 dark:text-zinc-200 hover:bg-purple-50 dark:hover:bg-purple-950/40 transition-colors cursor-pointer font-medium text-xs"
                        >
                            {copiedKey ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                            <span>{copiedKey ? t('network_page.copied', 'Copied!') : t('network_page.copy_key', 'Copy')}</span>
                        </button>
                        <button
                            type="button"
                            onClick={handleDownloadKey}
                            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white dark:bg-zinc-800 border border-purple-200 dark:border-purple-900/50 text-gray-700 dark:text-zinc-200 hover:bg-purple-50 dark:hover:bg-purple-950/40 transition-colors cursor-pointer font-medium text-xs"
                        >
                            <Download className="w-3.5 h-3.5" />
                            <span>{t('network_page.download_key', 'Download')}</span>
                        </button>
                    </div>
                </div>
            </div>

            {/* Allowed Devices (Peers) Section */}
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <div>
                        <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-zinc-400">
                            {t('network_page.allowed_peers', 'Authorized Devices (Peers)')} ({peers.length})
                        </h4>
                        <p className="text-[11px] text-gray-400 dark:text-zinc-500">
                            {t('network_page.peers_subtitle', 'Manage client devices with permission to connect')}
                        </p>
                    </div>
                </div>

                {peers.length === 0 ? (
                    <div className="p-4 rounded-xl border border-dashed border-gray-200 dark:border-zinc-800 text-center text-xs text-gray-400 dark:text-zinc-500">
                        {t('network_page.no_peers', 'No client devices have been authorized yet.')}
                    </div>
                ) : (
                    <div className="border border-gray-100 dark:border-zinc-800 rounded-xl overflow-hidden divide-y divide-gray-100 dark:divide-zinc-800 text-xs">
                        {peers.map((peer, idx) => (
                            <div key={peer.name || idx} className="flex items-center justify-between p-3 bg-gray-50/40 dark:bg-zinc-800/30 hover:bg-gray-50 dark:hover:bg-zinc-800/60 transition-colors">
                                <div className="flex items-center gap-2.5">
                                    <Laptop className="w-4 h-4 text-purple-500" />
                                    <div>
                                        <span className="font-semibold text-gray-900 dark:text-zinc-100">
                                            {peer.name}
                                        </span>
                                        <span className="ml-2 font-mono text-[11px] text-gray-500 dark:text-zinc-400">
                                            ({peer.ip || '-'})
                                        </span>
                                    </div>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => onDeletePeer(peer.name)}
                                    title={t('network_page.delete_peer', 'Remove Device')}
                                    className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors cursor-pointer"
                                >
                                    <Trash2 className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                {/* Add Peer Form */}
                <form onSubmit={handleAddPeerSubmit} className="grid grid-cols-1 sm:grid-cols-12 gap-2 pt-1 text-xs">
                    <div className="sm:col-span-4">
                        <input
                            type="text"
                            value={newPeerName}
                            onChange={e => setNewPeerName(e.target.value)}
                            placeholder={t('network_page.peer_name', 'Device Name (e.g. iPhone)')}
                            className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white text-xs focus:ring-2 focus:ring-purple-500 focus:outline-none"
                        />
                    </div>
                    <div className="sm:col-span-6">
                        <input
                            type="text"
                            value={newPeerPubKey}
                            onChange={e => setNewPeerPubKey(e.target.value)}
                            placeholder={t('network_page.peer_pubkey', 'Device Public Key')}
                            className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-gray-900 dark:text-white font-mono text-xs focus:ring-2 focus:ring-purple-500 focus:outline-none"
                        />
                    </div>
                    <div className="sm:col-span-2">
                        <button
                            type="submit"
                            disabled={addingPeer || !newPeerName.trim() || !newPeerPubKey.trim()}
                            className="w-full h-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl font-semibold text-xs text-white bg-purple-600 hover:bg-purple-500 shadow-sm transition-all cursor-pointer disabled:opacity-50"
                        >
                            <Plus className="w-3.5 h-3.5" />
                            <span>{t('network_page.add_peer', 'Authorize')}</span>
                        </button>
                    </div>
                </form>
            </div>

            {/* WireGuard Client Setup Guide Toggle */}
            <div className="border border-gray-100 dark:border-zinc-800 rounded-xl overflow-hidden text-xs">
                <button
                    type="button"
                    onClick={() => setShowGuide(!showGuide)}
                    className="w-full flex items-center justify-between p-3.5 bg-gray-50/80 dark:bg-zinc-800/40 text-gray-700 dark:text-zinc-300 font-semibold cursor-pointer hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors"
                >
                    <span className="flex items-center gap-2">
                        <HelpCircle className="w-4 h-4 text-purple-500" />
                        {t('network_page.client_guide', 'WireGuard Client Setup Guide')}
                    </span>
                    {showGuide ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>

                {showGuide && (
                    <div className="p-4 space-y-3 bg-white dark:bg-zinc-900 border-t border-gray-100 dark:border-zinc-800 text-xs">
                        <p className="text-gray-600 dark:text-zinc-400 leading-relaxed">
                            {t(
                                'network_page.client_guide_desc',
                                'To connect, install the official WireGuard app on your phone or PC and import a configuration profile structured like this:'
                            )}
                        </p>
                        <div className="relative">
                            <pre className="p-3.5 rounded-xl bg-zinc-900 text-zinc-100 font-mono text-[11px] overflow-x-auto select-all">
                                {clientTemplate}
                            </pre>
                            <button
                                type="button"
                                onClick={handleCopyTemplate}
                                className="absolute top-2.5 right-2.5 inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/10 hover:bg-white/20 text-white text-[10px] font-semibold transition-colors cursor-pointer"
                            >
                                {copiedTemplate ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                                <span>{copiedTemplate ? t('network_page.copied', 'Copied!') : t('network_page.copy_config', 'Copy')}</span>
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
