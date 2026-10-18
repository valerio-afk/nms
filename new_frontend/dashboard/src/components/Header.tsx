import { useState, useRef, useEffect } from 'react';
import { 
    LayoutDashboard, 
    HardDrive, 
    Network, 
    Users, 
    Terminal, 
    Settings, 
    Sun, 
    Moon, 
    ChevronDown, 
    Check, 
    Power, 
    LogOut, 
    RotateCcw, 
    Menu,
    X
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { User } from '@nms/shared';

export interface HeaderProps {
    currentUser: User | null;
    activeTab: string;
    setActiveTab: (tab: string) => void;
    onTriggerPowerAction: (action: 'logout' | 'reboot' | 'shutdown') => void;
    isDark: boolean;
    setIsDark: (dark: boolean) => void;
}

export default function Header({
    currentUser,
    activeTab,
    setActiveTab,
    onTriggerPowerAction,
    isDark,
    setIsDark
}: HeaderProps) {
    const { t, i18n } = useTranslation();
    const [isLangMenuOpen, setIsLangMenuOpen] = useState(false);
    const [isPowerMenuOpen, setIsPowerMenuOpen] = useState(false);
    const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

    const langMenuRef = useRef<HTMLDivElement>(null);
    const powerMenuRef = useRef<HTMLDivElement>(null);

    // Close menus on outside click
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (langMenuRef.current && !langMenuRef.current.contains(e.target as Node)) {
                setIsLangMenuOpen(false);
            }
            if (powerMenuRef.current && !powerMenuRef.current.contains(e.target as Node)) {
                setIsPowerMenuOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const navItems = [
        { id: 'dashboard', label: t('nav.dashboard', 'Dashboard'), icon: LayoutDashboard },
        { id: 'disks', label: t('nav.disks', 'Disk Management'), icon: HardDrive },
        { id: 'network', label: t('nav.network', 'Network'), icon: Network },
        { id: 'users', label: t('nav.users', 'Users'), icon: Users },
        { id: 'access', label: t('nav.access', 'Remote Access'), icon: Terminal },
        { id: 'advanced', label: t('nav.advanced', 'Advanced'), icon: Settings },
    ];

    const userInitials = (currentUser?.visible_name || currentUser?.username || 'U')
        .slice(0, 2)
        .toUpperCase();

    return (
        <header className="sticky top-0 z-40 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-md shadow-xs ring-1 ring-gray-900/5 dark:ring-white/10 transition-colors duration-300">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-16 gap-4">
                    {/* Brand / Logo */}
                    <div className="flex items-center gap-6">
                        <div className="flex items-center gap-3">
                            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center text-white font-bold shadow-md shadow-indigo-500/20">
                                N
                            </div>
                            <h1 className="text-lg font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-500 to-purple-600 hidden sm:inline-block">
                                {t('app.title', 'NAS Management System')}
                            </h1>
                        </div>

                        {/* Desktop Navigation Links */}
                        <nav className="hidden md:flex items-center gap-1">
                            {navItems.map((item) => {
                                const Icon = item.icon;
                                const isActive = activeTab === item.id;
                                return (
                                    <button
                                        key={item.id}
                                        onClick={() => setActiveTab(item.id)}
                                        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                                            isActive
                                                ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 font-semibold'
                                                : 'text-gray-600 dark:text-zinc-400 hover:bg-gray-100 dark:hover:bg-zinc-800 hover:text-gray-900 dark:hover:text-zinc-200'
                                        }`}
                                    >
                                        <Icon className="w-4 h-4" />
                                        <span>{item.label}</span>
                                    </button>
                                );
                            })}
                        </nav>
                    </div>

                    {/* Right Side Actions */}
                    <div className="flex items-center gap-2 sm:gap-3">
                        {/* Language Selector */}
                        <div className="relative" ref={langMenuRef}>
                            <button
                                onClick={() => setIsLangMenuOpen(!isLangMenuOpen)}
                                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs sm:text-sm font-medium bg-gray-100 dark:bg-zinc-800 rounded-lg text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-zinc-700 transition-colors cursor-pointer"
                                aria-label="Select Language"
                            >
                                <span>{i18n.language.startsWith('it') ? '🇮🇹 IT' : '🇬🇧 EN'}</span>
                                <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isLangMenuOpen ? 'rotate-180' : ''}`} />
                            </button>

                            {isLangMenuOpen && (
                                <div className="absolute right-0 mt-2 w-36 bg-white dark:bg-zinc-800 rounded-xl shadow-lg border border-gray-100 dark:border-zinc-700 overflow-hidden z-50 animate-in fade-in zoom-in-95 duration-150">
                                    <div className="py-1">
                                        <button
                                            onClick={() => {
                                                i18n.changeLanguage('en');
                                                localStorage.setItem('appLanguage', 'en');
                                                setIsLangMenuOpen(false);
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
                                                setIsLangMenuOpen(false);
                                            }}
                                            className="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-zinc-700/50 cursor-pointer"
                                        >
                                            <span>🇮🇹 Italiano</span>
                                            {i18n.language.startsWith('it') && <Check className="w-3.5 h-3.5 text-indigo-500" />}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Dark Mode Toggle */}
                        <button
                            onClick={() => setIsDark(!isDark)}
                            className="p-2 text-gray-700 bg-gray-100 dark:text-gray-200 dark:bg-zinc-800 rounded-lg hover:bg-gray-200 dark:hover:bg-zinc-700 transition-colors cursor-pointer"
                            aria-label="Toggle Dark Mode"
                        >
                            {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                        </button>

                        {/* User Initials & Notification Badge */}
                        <div className="relative flex items-center">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-indigo-700 text-white font-semibold flex items-center justify-center text-xs shadow-xs">
                                {userInitials}
                            </div>
                            {(currentUser?.notifications || 0) > 0 && (
                                <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white ring-2 ring-white dark:ring-zinc-900">
                                    {currentUser?.notifications}
                                </span>
                            )}
                        </div>

                        {/* Power Menu (Logout, Reboot, Shutdown) */}
                        <div className="relative" ref={powerMenuRef}>
                            <button
                                onClick={() => setIsPowerMenuOpen(!isPowerMenuOpen)}
                                className="p-2 text-gray-700 bg-gray-100 dark:text-gray-200 dark:bg-zinc-800 rounded-lg hover:bg-gray-200 dark:hover:bg-zinc-700 transition-colors cursor-pointer hover:text-red-500"
                                aria-label="System Power Options"
                            >
                                <Power className="w-4 h-4" />
                            </button>

                            {isPowerMenuOpen && (
                                <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-zinc-800 rounded-xl shadow-lg border border-gray-100 dark:border-zinc-700 overflow-hidden z-50 animate-in fade-in zoom-in-95 duration-150">
                                    <div className="p-2 border-b border-gray-100 dark:border-zinc-700 text-xs font-semibold text-gray-500 dark:text-zinc-400">
                                        {currentUser?.username ? `@${currentUser.username}` : t('actions.power', 'System')}
                                    </div>
                                    <div className="py-1">
                                        <button
                                            onClick={() => {
                                                setIsPowerMenuOpen(false);
                                                onTriggerPowerAction('logout');
                                            }}
                                            className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-zinc-700/60 cursor-pointer"
                                        >
                                            <LogOut className="w-3.5 h-3.5 text-gray-500" />
                                            <span>{t('actions.logout', 'Logout')}</span>
                                        </button>
                                        <button
                                            onClick={() => {
                                                setIsPowerMenuOpen(false);
                                                onTriggerPowerAction('reboot');
                                            }}
                                            className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/40 cursor-pointer"
                                        >
                                            <RotateCcw className="w-3.5 h-3.5" />
                                            <span>{t('actions.reboot', 'Reboot System')}</span>
                                        </button>
                                        <button
                                            onClick={() => {
                                                setIsPowerMenuOpen(false);
                                                onTriggerPowerAction('shutdown');
                                            }}
                                            className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 cursor-pointer"
                                        >
                                            <Power className="w-3.5 h-3.5" />
                                            <span>{t('actions.shutdown', 'Power Off')}</span>
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Mobile Hamburger Button */}
                        <button
                            onClick={() => setIsMobileNavOpen(!isMobileNavOpen)}
                            className="md:hidden p-2 text-gray-700 bg-gray-100 dark:text-gray-200 dark:bg-zinc-800 rounded-lg hover:bg-gray-200 dark:hover:bg-zinc-700 cursor-pointer"
                            aria-label="Toggle Navigation"
                        >
                            {isMobileNavOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
                        </button>
                    </div>
                </div>

                {/* Mobile Navigation Dropdown */}
                {isMobileNavOpen && (
                    <div className="md:hidden border-t border-gray-100 dark:border-zinc-800 py-3 space-y-1">
                        {navItems.map((item) => {
                            const Icon = item.icon;
                            const isActive = activeTab === item.id;
                            return (
                                <button
                                    key={item.id}
                                    onClick={() => {
                                        setActiveTab(item.id);
                                        setIsMobileNavOpen(false);
                                    }}
                                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors cursor-pointer ${
                                        isActive
                                            ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400'
                                            : 'text-gray-700 dark:text-zinc-300 hover:bg-gray-100 dark:hover:bg-zinc-800'
                                    }`}
                                >
                                    <Icon className="w-4 h-4" />
                                    <span>{item.label}</span>
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>
        </header>
    );
}
