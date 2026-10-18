import { useState, useEffect } from 'react';
import { Login, getCurrentUser, logout as apiLogout, setAuthToken, type User } from '@nms/shared';
import Header from './components/Header';
import ConfirmModal from './components/ConfirmModal';
import DashboardPage from './pages/DashboardPage';
import PlaceholderPage from './pages/PlaceholderPage';
import { rebootSystem, shutdownSystem } from './utils/api';
import { useTranslation } from 'react-i18next';
import { Sun, Moon, ChevronDown, Check } from 'lucide-react';

export default function App() {
    const { t, i18n } = useTranslation();
    const searchParams = new URLSearchParams(window.location.search);
    const isDemoMode = searchParams.get('demo') === 'true';
    const [isLoggedIn, setIsLoggedIn] = useState(() => isDemoMode || !!localStorage.getItem('authToken'));
    const [currentUser, setCurrentUser] = useState<User | null>(() => {
        if (isDemoMode) {
            return {
                username: 'admin',
                visible_name: 'Administrator',
                admin: true,
                sudo: true,
                notifications: 2
            };
        }
        return null;
    });
    const [authError, setAuthError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState('dashboard');
    const [isDark, setIsDark] = useState(() => {
        const saved = localStorage.getItem('theme');
        return saved ? saved === 'dark' : true;
    });

    // Language dropdown state on Login screen
    const [isLoginLangOpen, setIsLoginLangOpen] = useState(false);

    // Power Confirmation Modal
    const [confirmModal, setConfirmModal] = useState<{
        isOpen: boolean;
        action: 'logout' | 'reboot' | 'shutdown' | null;
        isLoading: boolean;
    }>({
        isOpen: false,
        action: null,
        isLoading: false
    });

    // Theme toggling on document.documentElement
    useEffect(() => {
        if (isDark) {
            document.documentElement.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        } else {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('theme', 'light');
        }
    }, [isDark]);

    // Check user profile on mount if token exists
    useEffect(() => {
        if (!isLoggedIn) return;

        let isMounted = true;
        getCurrentUser()
            .then((user) => {
                if (isMounted) {
                    if (user) {
                        setCurrentUser(user);
                    } else {
                        setIsLoggedIn(false);
                        setAuthToken('');
                    }
                }
            })
            .catch((err) => {
                console.error('Failed to get current user', err);
                if (isMounted) {
                    setIsLoggedIn(false);
                    setAuthToken('');
                }
            });

        return () => {
            isMounted = false;
        };
    }, [isLoggedIn]);

    const handleLoginSuccess = async (username: string) => {
        setIsLoggedIn(true);
        setAuthError(null);
        try {
            const user = await getCurrentUser();
            if (user) {
                setCurrentUser(user);
            } else {
                setCurrentUser({
                    username,
                    visible_name: username,
                    admin: true,
                    sudo: true,
                    notifications: 0
                });
            }
        } catch {
            setCurrentUser({
                username,
                visible_name: username,
                admin: true,
                sudo: true,
                notifications: 0
            });
        }
    };

    const handleTriggerPowerAction = (action: 'logout' | 'reboot' | 'shutdown') => {
        setConfirmModal({
            isOpen: true,
            action,
            isLoading: false
        });
    };

    const handleExecutePowerAction = async () => {
        const action = confirmModal.action;
        if (!action) return;

        setConfirmModal(prev => ({ ...prev, isLoading: true }));
        try {
            if (action === 'logout') {
                await apiLogout();
            } else if (action === 'reboot') {
                await rebootSystem();
            } else if (action === 'shutdown') {
                await shutdownSystem();
            }
        } catch (e) {
            console.error(`Failed to execute ${action}`, e);
        } finally {
            setConfirmModal({ isOpen: false, action: null, isLoading: false });
            setIsLoggedIn(false);
            setCurrentUser(null);
            setAuthToken('');
            setActiveTab('dashboard');
        }
    };

    // If NOT logged in, show shared Login page with top-right language & theme controls
    if (!isLoggedIn) {
        const loginHeaderControls = (
            <div className="flex items-center gap-2">
                {/* Language Switcher */}
                <div className="relative">
                    <button
                        onClick={() => setIsLoginLangOpen(!isLoginLangOpen)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white dark:bg-zinc-800 rounded-lg text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-zinc-700 shadow-xs cursor-pointer hover:bg-gray-50 dark:hover:bg-zinc-700"
                    >
                        <span>{i18n.language.startsWith('it') ? '🇮🇹 IT' : '🇬🇧 EN'}</span>
                        <ChevronDown className="w-3.5 h-3.5" />
                    </button>

                    {isLoginLangOpen && (
                        <div className="absolute right-0 mt-2 w-32 bg-white dark:bg-zinc-800 rounded-xl shadow-lg border border-gray-100 dark:border-zinc-700 overflow-hidden z-50">
                            <button
                                onClick={() => {
                                    i18n.changeLanguage('en');
                                    localStorage.setItem('appLanguage', 'en');
                                    setIsLoginLangOpen(false);
                                }}
                                className="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-zinc-700/50 cursor-pointer"
                            >
                                <span>🇬🇧 English</span>
                                {i18n.language.startsWith('en') && <Check className="w-3.5 h-3.5 text-indigo-500" />}
                            </button>
                            <button
                                onClick={() => {
                                    i18n.changeLanguage('it');
                                    localStorage.setItem('appLanguage', 'it');
                                    setIsLoginLangOpen(false);
                                }}
                                className="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-zinc-700/50 cursor-pointer"
                            >
                                <span>🇮🇹 Italiano</span>
                                {i18n.language.startsWith('it') && <Check className="w-3.5 h-3.5 text-indigo-500" />}
                            </button>
                        </div>
                    )}
                </div>

                {/* Theme Toggle */}
                <button
                    onClick={() => setIsDark(!isDark)}
                    className="p-2 text-gray-700 bg-white dark:text-gray-200 dark:bg-zinc-800 rounded-lg border border-gray-200 dark:border-zinc-700 shadow-xs hover:bg-gray-50 dark:hover:bg-zinc-700 transition-colors cursor-pointer"
                    aria-label="Toggle Theme"
                >
                    {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                </button>
            </div>
        );

        return (
            <Login
                onLoginSuccess={handleLoginSuccess}
                initialError={authError}
                appName={t('app.title', 'NAS Management System')}
                title={t('login.secure_access', 'Secure Access')}
                subtitle={t('login.subtitle', 'Please authenticate to access the dashboard')}
                headerRightContent={loginHeaderControls}
            />
        );
    }

    // Modal texts for power actions
    const modalTexts = {
        logout: {
            title: t('actions.logout', 'Logout'),
            message: t('actions.logout_confirm', 'Are you sure you want to log out of your session?'),
            confirmText: t('actions.logout', 'Logout'),
            variant: 'danger' as const
        },
        reboot: {
            title: t('actions.reboot', 'Reboot System'),
            message: t('actions.reboot_confirm', 'Are you sure you want to reboot the system? All active services will temporarily disconnect.'),
            confirmText: t('actions.reboot', 'Reboot'),
            variant: 'warning' as const
        },
        shutdown: {
            title: t('actions.shutdown', 'Power Off System'),
            message: t('actions.shutdown_confirm', 'Are you sure you want to completely power off the NAS?'),
            confirmText: t('actions.shutdown', 'Power Off'),
            variant: 'danger' as const
        }
    };

    const currentModalInfo = confirmModal.action ? modalTexts[confirmModal.action] : null;

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-zinc-950 text-gray-900 dark:text-gray-100 flex flex-col transition-colors duration-300">
            <Header
                currentUser={currentUser}
                activeTab={activeTab}
                setActiveTab={setActiveTab}
                onTriggerPowerAction={handleTriggerPowerAction}
                isDark={isDark}
                setIsDark={setIsDark}
            />

            <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
                {activeTab === 'dashboard' ? (
                    <DashboardPage currentUser={currentUser} />
                ) : (
                    <PlaceholderPage
                        title={
                            activeTab === 'disks'
                                ? t('nav.disks', 'Disk Management')
                                : activeTab === 'network'
                                ? t('nav.network', 'Network')
                                : activeTab === 'users'
                                ? t('nav.users', 'Users')
                                : activeTab === 'access'
                                ? t('nav.access', 'Remote Access')
                                : t('nav.advanced', 'Advanced')
                        }
                        onBack={() => setActiveTab('dashboard')}
                    />
                )}
            </main>

            {currentModalInfo && (
                <ConfirmModal
                    isOpen={confirmModal.isOpen}
                    title={currentModalInfo.title}
                    message={currentModalInfo.message}
                    confirmText={currentModalInfo.confirmText}
                    confirmVariant={currentModalInfo.variant}
                    isLoading={confirmModal.isLoading}
                    onConfirm={handleExecutePowerAction}
                    onCancel={() => setConfirmModal({ isOpen: false, action: null, isLoading: false })}
                />
            )}
        </div>
    );
}
