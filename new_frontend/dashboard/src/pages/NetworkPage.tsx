import { useState, useEffect, useCallback } from 'react';
import {
    Network,
    RotateCw,
    ArrowLeft,
    CheckCircle2,
    Shield,
    Globe
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { NetworkInterfaceItem } from '../types/dashboard';
import type { VpnPeerItem, DdnsProviderItem } from '../types/network';
import {
    fetchNetworks,
    setIfaceStatus,
    fetchVpnEndpoint,
    fetchVpnPublicKey,
    updateVpnConfig,
    generateVpnKeys,
    fetchVpnPeers,
    addVpnPeer,
    deleteVpnPeer,
    fetchDdnsProviders,
    fetchDdnsProtocols,
    addDdnsProvider,
    editDdnsProvider,
    deleteDdnsProvider,
    connectWifi,
    enableHotspot
} from '../utils/api';
import { useToast } from '../context/ToastContext';
import InterfaceCard from '../components/network/InterfaceCard';
import VpnCard from '../components/network/VpnCard';
import DdnsCard from '../components/network/DdnsCard';
import ConfirmModal from '../components/ConfirmModal';

interface NetworkPageProps {
    onNavigate?: (tab: string) => void;
}

export default function NetworkPage({ onNavigate }: NetworkPageProps) {
    const { t } = useTranslation();
    const { toastSuccess, toastError } = useToast();

    // Data states
    const [interfaces, setInterfaces] = useState<NetworkInterfaceItem[]>([]);
    const [vpnIface, setVpnIface] = useState<NetworkInterfaceItem | null>(null);
    const [vpnEndpoint, setVpnEndpoint] = useState<string | null>(null);
    const [vpnPublicKey, setVpnPublicKey] = useState<string | null>(null);
    const [vpnPeers, setVpnPeers] = useState<VpnPeerItem[]>([]);
    const [ddnsProviders, setDdnsProviders] = useState<DdnsProviderItem[]>([]);
    const [ddnsProtocols, setDdnsProtocols] = useState<string[]>([]);

    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    // Active Section Filter / Tab (optional quick scroll or unified view)
    const [activeSection, setActiveSection] = useState<'all' | 'interfaces' | 'vpn' | 'ddns'>('all');

    // Confirm Modal
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

    const loadData = useCallback(async (isManual = false) => {
        if (isManual) setRefreshing(true);
        try {
            const isDemo = typeof window !== 'undefined' && window.location.search.includes('demo=true');

            if (isDemo) {
                // Mock network data for demo mode
                const mockIfaces: NetworkInterfaceItem[] = [
                    {
                        name: 'eth0',
                        enabled: true,
                        status: 'up',
                        network_name: 'Wired Connection 1',
                        type: 'ethernet',
                        ipv4: {
                            dynamic: true,
                            address: '192.168.1.180',
                            netmask: '255.255.255.0',
                            gateway: '192.168.1.1',
                            dns: ['1.1.1.1', '8.8.8.8']
                        },
                        ipv6: {
                            enabled: true,
                            address: 'fe80::1ff:fe23:4567/64'
                        },
                        rxBytes: 154829012,
                        txBytes: 89324012
                    },
                    {
                        name: 'wlan0',
                        enabled: false,
                        status: 'down',
                        network_name: 'Home_WiFi_5G',
                        type: 'wifi',
                        ipv4: null,
                        ipv6: null,
                        rxBytes: 1204012,
                        txBytes: 492012
                    }
                ];

                const mockVpn: NetworkInterfaceItem = {
                    name: 'vpn',
                    enabled: true,
                    status: 'up',
                    network_name: 'VPN',
                    type: 'vpn',
                    ipv4: {
                        dynamic: false,
                        address: '10.8.0.1',
                        netmask: '255.255.255.0'
                    }
                };

                setInterfaces(mockIfaces);
                setVpnIface(mockVpn);
                setVpnEndpoint('93.184.216.34');
                setVpnPublicKey('aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5zA7bC9d=');
                setVpnPeers([
                    { name: 'iPhone-Admin', ip: '10.8.0.2' },
                    { name: 'MacBook-Pro', ip: '10.8.0.3' }
                ]);
                setDdnsProviders([
                    {
                        name: 'home-duckdns',
                        enabled: true,
                        protocol: 'duckdns',
                        hostname: 'myhome.duckdns.org',
                        server: 'www.duckdns.org'
                    }
                ]);
                setDdnsProtocols(['duckdns', 'noip', 'dynu', 'freedns', 'dnsexit', 'dynv6', 'cloudns']);
                return;
            }

            const [
                ifacesRes,
                endpointRes,
                pubkeyRes,
                peersRes,
                ddnsRes,
                protoRes
            ] = await Promise.allSettled([
                fetchNetworks(),
                fetchVpnEndpoint(),
                fetchVpnPublicKey(),
                fetchVpnPeers(),
                fetchDdnsProviders(),
                fetchDdnsProtocols()
            ]);

            if (ifacesRes.status === 'fulfilled') {
                const allIfaces = ifacesRes.value;
                // Separate vpn interface from standard network adapters
                const vpnItem = allIfaces.find(i => i.name === 'vpn' || i.type === 'vpn') || null;
                const physicalIfaces = allIfaces.filter(i => i.name !== 'vpn' && i.type !== 'vpn');
                setInterfaces(physicalIfaces);
                setVpnIface(vpnItem);
            }

            if (endpointRes.status === 'fulfilled') setVpnEndpoint(endpointRes.value);
            if (pubkeyRes.status === 'fulfilled') setVpnPublicKey(pubkeyRes.value);
            if (peersRes.status === 'fulfilled') {
                setVpnPeers(peersRes.value.map(([name, ip]) => ({ name, ip })));
            }
            if (ddnsRes.status === 'fulfilled') {
                const providersObj = ddnsRes.value;
                const providersList: DdnsProviderItem[] = Object.entries(providersObj).map(([name, cfg]) => ({
                    name,
                    enabled: !!cfg.enabled,
                    protocol: cfg.protocol || 'duckdns',
                    server: cfg.server || undefined,
                    username: cfg.username || undefined,
                    password: cfg.password || undefined,
                    hostname: cfg.hostname || undefined
                }));
                setDdnsProviders(providersList);
            }
            if (protoRes.status === 'fulfilled') setDdnsProtocols(protoRes.value);

        } catch (err: any) {
            console.error('Failed to load network data', err);
            if (isManual) {
                toastError(err?.message || t('network_page.feedback.iface_status_error', 'Failed to retrieve network details'));
            }
        } finally {
            setLoading(false);
            if (isManual) setRefreshing(false);
        }
    }, [t, toastError]);

    // Initial fetch and 3000ms periodic background polling (matching Flask GlobalRefresher)
    useEffect(() => {
        loadData();
        const timer = setInterval(() => {
            loadData(false);
        }, 3000);
        return () => clearInterval(timer);
    }, [loadData]);

    // Handlers
    const handleToggleIface = async (ifaceName: string, action: 'up' | 'down') => {
        try {
            await setIfaceStatus(ifaceName, action);
            toastSuccess(t('network_page.feedback.iface_status_success', {
                iface: ifaceName,
                status: action === 'up' ? t('network_page.status_up', 'Connected') : t('network_page.status_down', 'Disconnected')
            }));
            await loadData(true);
        } catch (err: any) {
            toastError(err?.message || t('network_page.feedback.iface_status_error', { iface: ifaceName }));
        }
    };

    const handleConnectWifi = async (ifaceName: string, ssid: string, psk?: string | null, profile?: string | null) => {
        try {
            toastSuccess(t('network_page.feedback.wifi_connected', { ssid }));
            await connectWifi(ifaceName, { ssid, psk, profile });
            await loadData(true);
        } catch (err: any) {
            toastError(err?.message || t('network_page.feedback.wifi_error', 'Failed to connect to Wi-Fi.'));
        }
    };

    const handleEnableHotspot = async (ifaceName: string, ssid: string, psk?: string | null) => {
        try {
            await enableHotspot({ iface: ifaceName, ssid, psk });
            toastSuccess(t('network_page.feedback.hotspot_enabled', { ssid }));
            await loadData(true);
        } catch (err: any) {
            toastError(err?.message || t('network_page.feedback.hotspot_error', 'Failed to enable hotspot.'));
        }
    };

    const handleToggleVpn = async (action: 'up' | 'down') => {
        try {
            await setIfaceStatus('vpn', action);
            toastSuccess(t('network_page.feedback.vpn_status_success', {
                status: action === 'up' ? t('network_page.status_up', 'Active') : t('network_page.status_down', 'Disabled')
            }));
            await loadData(true);
        } catch (err: any) {
            toastError(err?.message || t('network_page.feedback.iface_status_error', { iface: 'VPN' }));
        }
    };

    const handleSaveVpnConfig = async (cfg: { address: string; netmask: string; endpoint: string }) => {
        try {
            await updateVpnConfig(cfg);
            toastSuccess(t('network_page.feedback.vpn_config_saved', 'VPN server configuration saved successfully.'));
            await loadData(true);
        } catch (err: any) {
            toastError(err?.message || t('common.error', 'Failed to save VPN configuration.'));
        }
    };

    const handleGenKeys = async () => {
        setConfirmModal({
            isOpen: true,
            title: t('network_page.gen_keys', 'Regenerate Server Keys'),
            message: t('network_page.gen_keys_confirm', 'Regenerating keys will invalidate the current key and disconnect all existing clients. Proceed?'),
            confirmText: t('network_page.gen_keys', 'Regenerate Keys'),
            variant: 'warning',
            onConfirm: async () => {
                setConfirmModal(prev => ({ ...prev, isLoading: true }));
                try {
                    await generateVpnKeys();
                    toastSuccess(t('network_page.feedback.vpn_keys_generated', 'New WireGuard cryptographic keys generated successfully.'));
                    await loadData(true);
                } catch (err: any) {
                    toastError(err?.message || t('common.error', 'Failed to regenerate server keys.'));
                } finally {
                    setConfirmModal(prev => ({ ...prev, isOpen: false, isLoading: false }));
                }
            }
        });
    };

    const handleAddPeer = async (name: string, publicKey: string) => {
        try {
            await addVpnPeer(name, publicKey);
            toastSuccess(t('network_page.feedback.peer_added', { name }));
            await loadData(true);
        } catch (err: any) {
            toastError(err?.message || t('common.error', 'Failed to add peer.'));
        }
    };

    const handleDeletePeer = async (name: string) => {
        setConfirmModal({
            isOpen: true,
            title: t('network_page.delete_peer', 'Remove Device'),
            message: t('network_page.delete_peer_confirm', { name }),
            confirmText: t('common.delete', 'Delete'),
            variant: 'danger',
            onConfirm: async () => {
                setConfirmModal(prev => ({ ...prev, isLoading: true }));
                try {
                    await deleteVpnPeer(name);
                    toastSuccess(t('network_page.feedback.peer_deleted', { name }));
                    await loadData(true);
                } catch (err: any) {
                    toastError(err?.message || t('common.error', 'Failed to remove peer.'));
                } finally {
                    setConfirmModal(prev => ({ ...prev, isOpen: false, isLoading: false }));
                }
            }
        });
    };

    const handleAddDdns = async (payload: {
        name: string;
        proto: string;
        server?: string;
        username?: string;
        password?: string;
        hostname?: string;
    }) => {
        try {
            await addDdnsProvider(payload);
            toastSuccess(t('network_page.feedback.ddns_added', { name: payload.name }));
            await loadData(true);
        } catch (err: any) {
            toastError(err?.message || t('common.error', 'Failed to add DDNS provider.'));
        }
    };

    const handleEditDdns = async (payload: {
        name: string;
        enabled: boolean;
        proto: string;
        server?: string;
        username?: string;
        password?: string;
        hostname?: string;
    }) => {
        try {
            await editDdnsProvider(payload);
            toastSuccess(t('network_page.feedback.ddns_updated', { name: payload.name }));
            await loadData(true);
        } catch (err: any) {
            toastError(err?.message || t('common.error', 'Failed to update DDNS provider.'));
        }
    };

    const handleDeleteDdns = async (name: string) => {
        setConfirmModal({
            isOpen: true,
            title: t('network_page.delete_ddns', 'Delete Provider'),
            message: t('network_page.delete_ddns_confirm', { name }),
            confirmText: t('common.delete', 'Delete'),
            variant: 'danger',
            onConfirm: async () => {
                setConfirmModal(prev => ({ ...prev, isLoading: true }));
                try {
                    await deleteDdnsProvider(name);
                    toastSuccess(t('network_page.feedback.ddns_deleted', { name }));
                    await loadData(true);
                } catch (err: any) {
                    toastError(err?.message || t('common.error', 'Failed to delete DDNS provider.'));
                } finally {
                    setConfirmModal(prev => ({ ...prev, isOpen: false, isLoading: false }));
                }
            }
        });
    };

    const activeCount = interfaces.filter(i => i.enabled && i.status === 'up').length;

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
                                {t('nav.network', 'Network')}
                            </span>
                        </div>
                        <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mt-0.5">
                            {t('network_page.page_title', 'Network Management')}
                        </h2>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {/* Section filter pills */}
                    <div className="hidden md:flex items-center p-1 rounded-xl bg-gray-100 dark:bg-zinc-800/80 text-xs font-medium">
                        <button
                            type="button"
                            onClick={() => setActiveSection('all')}
                            className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                                activeSection === 'all'
                                    ? 'bg-white dark:bg-zinc-700 text-gray-900 dark:text-white shadow-xs font-semibold'
                                    : 'text-gray-600 dark:text-zinc-400 hover:text-gray-900'
                            }`}
                        >
                            {t('common.all', 'All')}
                        </button>
                        <button
                            type="button"
                            onClick={() => setActiveSection('interfaces')}
                            className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                                activeSection === 'interfaces'
                                    ? 'bg-white dark:bg-zinc-700 text-gray-900 dark:text-white shadow-xs font-semibold'
                                    : 'text-gray-600 dark:text-zinc-400 hover:text-gray-900'
                            }`}
                        >
                            {t('network_page.interfaces_title', 'Adapters')}
                        </button>
                        <button
                            type="button"
                            onClick={() => setActiveSection('vpn')}
                            className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                                activeSection === 'vpn'
                                    ? 'bg-white dark:bg-zinc-700 text-gray-900 dark:text-white shadow-xs font-semibold'
                                    : 'text-gray-600 dark:text-zinc-400 hover:text-gray-900'
                            }`}
                        >
                            WireGuard
                        </button>
                        <button
                            type="button"
                            onClick={() => setActiveSection('ddns')}
                            className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                                activeSection === 'ddns'
                                    ? 'bg-white dark:bg-zinc-700 text-gray-900 dark:text-white shadow-xs font-semibold'
                                    : 'text-gray-600 dark:text-zinc-400 hover:text-gray-900'
                            }`}
                        >
                            DDNS
                        </button>
                    </div>

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

            {/* Loading Pulse Skeleton */}
            {loading && interfaces.length === 0 ? (
                <div className="space-y-6 animate-pulse">
                    {/* Overview Banner Skeleton */}
                    <div className="h-28 rounded-2xl bg-gray-200 dark:bg-zinc-800/60" />

                    {/* Interfaces Grid Skeleton */}
                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <div className="h-5 w-40 rounded-lg bg-gray-200 dark:bg-zinc-800/60" />
                            <div className="h-4 w-24 rounded-lg bg-gray-200 dark:bg-zinc-800/60" />
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {[1, 2].map(i => (
                                <div key={i} className="h-56 rounded-2xl bg-gray-200 dark:bg-zinc-800/60" />
                            ))}
                        </div>
                    </div>

                    {/* VPN & DDNS Skeleton */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-2">
                        <div className="h-96 rounded-2xl bg-gray-200 dark:bg-zinc-800/60" />
                        <div className="h-96 rounded-2xl bg-gray-200 dark:bg-zinc-800/60" />
                    </div>
                </div>
            ) : (
                <>
                    {/* Network Overview Summary Banner */}
                    <div className="p-6 rounded-2xl bg-gradient-to-r from-sky-500/10 via-indigo-500/5 to-transparent border border-sky-500/20 dark:border-sky-500/30">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                            <div className="flex items-center gap-3.5">
                                <div className="p-2.5 rounded-xl bg-sky-600 text-white shadow-md shadow-sky-600/20">
                                    <Network className="w-5 h-5" />
                                </div>
                                <div>
                                    <div className="flex items-center gap-2">
                                        <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                                            {t('network_page.interfaces_title', 'Network Adapters')}
                                        </h3>
                                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/50">
                                            <CheckCircle2 className="w-3.5 h-3.5" />
                                            <span>{activeCount} {t('widgets.network.active_interfaces', 'Active')}</span>
                                        </span>
                                    </div>
                                    <p className="text-xs text-gray-500 dark:text-zinc-400 mt-0.5">
                                        {interfaces.length} {t('widgets.network.total_interfaces', 'total interfaces detected')}
                                    </p>
                                </div>
                            </div>

                            {/* Quick status pills */}
                            <div className="flex flex-wrap items-center gap-2 text-xs">
                                <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-xl border font-medium ${
                                    vpnIface?.enabled
                                        ? 'bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300 border-purple-200 dark:border-purple-800/50'
                                        : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700'
                                }`}>
                                    <Shield className="w-3.5 h-3.5" />
                                    <span>VPN: {vpnIface?.enabled ? t('network_page.status_enabled', 'Active') : t('network_page.status_disabled', 'Inactive')}</span>
                                </span>
                                <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-xl border font-medium ${
                                    ddnsProviders.some(p => p.enabled)
                                        ? 'bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300 border-sky-200 dark:border-sky-800/50'
                                        : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700'
                                }`}>
                                    <Globe className="w-3.5 h-3.5" />
                                    <span>DDNS: {ddnsProviders.filter(p => p.enabled).length} {t('network_page.status_enabled', 'Active')}</span>
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Section 1: Physical & Wireless Adapters */}
                    {(activeSection === 'all' || activeSection === 'interfaces') && (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h3 className="text-base font-bold text-gray-900 dark:text-white">
                                        {t('network_page.interfaces_title', 'Network Adapters')}
                                    </h3>
                                    <p className="text-xs text-gray-500 dark:text-zinc-400">
                                        {t('network_page.interfaces_subtitle', 'Physical and wireless network connections')}
                                    </p>
                                </div>
                                <span className="text-xs font-mono text-gray-400 dark:text-zinc-500">
                                    {interfaces.length} {t('widgets.network.total_interfaces', 'interfaces')}
                                </span>
                            </div>

                            {interfaces.length === 0 ? (
                                <div className="p-8 rounded-2xl bg-white dark:bg-zinc-900 border border-gray-100 dark:border-zinc-800 text-center text-xs text-gray-500 dark:text-zinc-400">
                                    <Network className="w-8 h-8 mx-auto mb-2 opacity-40 text-gray-400" />
                                    <p>{t('network_page.no_interfaces', 'No network adapters were detected on this machine.')}</p>
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                    {interfaces.map(iface => (
                                        <InterfaceCard
                                            key={iface.name}
                                            iface={iface}
                                            onToggleStatus={handleToggleIface}
                                            onConnectWifi={handleConnectWifi}
                                            onEnableHotspot={handleEnableHotspot}
                                        />
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Section 2: WireGuard VPN & DDNS */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-2">
                        {(activeSection === 'all' || activeSection === 'vpn') && (
                            <VpnCard
                                vpnIface={vpnIface}
                                endpoint={vpnEndpoint}
                                publicKey={vpnPublicKey}
                                peers={vpnPeers}
                                onToggleVpn={handleToggleVpn}
                                onSaveConfig={handleSaveVpnConfig}
                                onGenKeys={handleGenKeys}
                                onAddPeer={handleAddPeer}
                                onDeletePeer={handleDeletePeer}
                            />
                        )}

                        {(activeSection === 'all' || activeSection === 'ddns') && (
                            <DdnsCard
                                providers={ddnsProviders}
                                protocols={ddnsProtocols}
                                onAddProvider={handleAddDdns}
                                onEditProvider={handleEditDdns}
                                onDeleteProvider={handleDeleteDdns}
                            />
                        )}
                    </div>
                </>
            )}

            {/* Confirm Modal */}
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
        </div>
    );
}
