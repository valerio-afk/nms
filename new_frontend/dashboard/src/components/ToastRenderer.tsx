import { useEffect, useState } from 'react';
import { X, AlertCircle, AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import { useToast, type Toast, type ToastVariant } from '../context/ToastContext';

const STYLES: Record<ToastVariant, {
    container: string;
    icon: string;
    progress: string;
    IconComponent: React.FC<{ className?: string }>;
}> = {
    error: {
        container: 'bg-white dark:bg-zinc-900 border-red-300 dark:border-red-800 text-gray-900 dark:text-white',
        icon: 'text-red-500 dark:text-red-400 bg-red-50 dark:bg-red-950/40',
        progress: 'bg-red-500',
        IconComponent: AlertCircle,
    },
    warning: {
        container: 'bg-white dark:bg-zinc-900 border-amber-300 dark:border-amber-700 text-gray-900 dark:text-white',
        icon: 'text-amber-500 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40',
        progress: 'bg-amber-500',
        IconComponent: AlertTriangle,
    },
    success: {
        container: 'bg-white dark:bg-zinc-900 border-emerald-300 dark:border-emerald-700 text-gray-900 dark:text-white',
        icon: 'text-emerald-500 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40',
        progress: 'bg-emerald-500',
        IconComponent: CheckCircle2,
    },
    info: {
        container: 'bg-white dark:bg-zinc-900 border-indigo-300 dark:border-indigo-700 text-gray-900 dark:text-white',
        icon: 'text-indigo-500 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/40',
        progress: 'bg-indigo-500',
        IconComponent: Info,
    },
};

function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: (id: string) => void }) {
    const style = STYLES[toast.variant];
    const { IconComponent } = style;
    // Animate the progress bar shrinking over `duration` ms
    const [width, setWidth] = useState(100);

    useEffect(() => {
        if (!toast.duration || toast.duration <= 0) return;
        const start = Date.now();
        let raf: number;
        const tick = () => {
            const elapsed = Date.now() - start;
            const remaining = Math.max(0, 100 - (elapsed / toast.duration!) * 100);
            setWidth(remaining);
            if (remaining > 0) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(raf);
    }, [toast.duration]);

    return (
        <div
            className={`
                relative flex items-start gap-3 w-full max-w-sm
                px-4 py-3 rounded-xl shadow-lg border
                animate-in slide-in-from-right-5 fade-in duration-200
                ${style.container}
            `}
        >
            {/* Icon */}
            <div className={`mt-0.5 p-1.5 rounded-lg shrink-0 ${style.icon}`}>
                <IconComponent className="w-4 h-4" />
            </div>

            {/* Text */}
            <div className="flex-1 min-w-0 pr-1">
                {toast.title && (
                    <p className="text-sm font-semibold leading-snug">{toast.title}</p>
                )}
                <p className={`text-xs leading-relaxed text-gray-600 dark:text-zinc-300 break-words ${toast.title ? 'mt-0.5' : 'text-sm font-medium text-gray-900 dark:text-white'}`}>
                    {toast.message}
                </p>
            </div>

            {/* Dismiss */}
            <button
                onClick={() => onRemove(toast.id)}
                className="shrink-0 mt-0.5 p-1 rounded-lg text-gray-400 hover:text-gray-700 dark:hover:text-zinc-200 hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                aria-label="Dismiss"
            >
                <X className="w-3.5 h-3.5" />
            </button>

            {/* Progress bar */}
            {toast.duration && toast.duration > 0 && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 rounded-b-xl overflow-hidden bg-gray-100 dark:bg-zinc-800">
                    <div
                        className={`h-full transition-none ${style.progress}`}
                        style={{ width: `${width}%` }}
                    />
                </div>
            )}
        </div>
    );
}

/** Renders all active toasts in a fixed corner stack. Mount once inside <App>. */
export default function ToastRenderer() {
    const { toasts, removeToast } = useToast();

    if (toasts.length === 0) return null;

    return (
        <div
            aria-live="polite"
            className="fixed bottom-5 right-5 z-[9998] flex flex-col gap-2.5 items-end pointer-events-none"
        >
            {toasts.map(toast => (
                <div key={toast.id} className="pointer-events-auto">
                    <ToastItem toast={toast} onRemove={removeToast} />
                </div>
            ))}
        </div>
    );
}
