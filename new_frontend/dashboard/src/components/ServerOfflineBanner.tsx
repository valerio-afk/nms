import { useState } from 'react';
import { WifiOff, RefreshCw, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { ServerStatus } from '../hooks/useServerStatus';

interface ServerOfflineBannerProps {
    status: ServerStatus;
}

export default function ServerOfflineBanner({ status }: ServerOfflineBannerProps) {
    const { t } = useTranslation();
    const [dismissed, setDismissed] = useState(false);

    // Reset dismiss state whenever we go from online → offline
    // so the banner comes back automatically on the next outage
    if (status === 'online' && dismissed) {
        setDismissed(false);
    }

    if (status === 'online' || dismissed) return null;

    const isReconnecting = status === 'reconnecting';

    return (
        <div
            role="alert"
            className={`
                fixed top-0 inset-x-0 z-[9999]
                flex items-center justify-between gap-3
                px-4 py-2.5
                text-sm font-medium text-white
                shadow-lg
                transition-all duration-300
                ${isReconnecting
                    ? 'bg-amber-500 dark:bg-amber-600'
                    : 'bg-red-600 dark:bg-red-700'}
            `}
        >
            {/* Left icon + message */}
            <div className="flex items-center gap-2 min-w-0">
                {isReconnecting ? (
                    <RefreshCw className="w-4 h-4 shrink-0 animate-spin" />
                ) : (
                    <WifiOff className="w-4 h-4 shrink-0" />
                )}
                <span className="truncate">
                    {isReconnecting
                        ? t('server.reconnecting', 'Attempting to reconnect to the server…')
                        : t('server.offline',      'Server is not reachable — data may be outdated')}
                </span>
            </div>

            {/* Dismiss button — only shown while offline (not reconnecting) */}
            {!isReconnecting && (
                <button
                    onClick={() => setDismissed(true)}
                    aria-label={t('common.close', 'Close')}
                    className="shrink-0 p-1 rounded hover:bg-white/20 transition-colors cursor-pointer"
                >
                    <X className="w-4 h-4" />
                </button>
            )}
        </div>
    );
}

