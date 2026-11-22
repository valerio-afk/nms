import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from 'react';

export type ToastVariant = 'error' | 'warning' | 'success' | 'info';

export interface Toast {
    id: string;
    variant: ToastVariant;
    title?: string;
    message: string;
    /** Auto-dismiss delay in ms. 0 = sticky (manual dismiss only). Default: 6000 for errors, 4000 others. */
    duration?: number;
}

interface ToastContextValue {
    toasts: Toast[];
    addToast: (toast: Omit<Toast, 'id'>) => void;
    removeToast: (id: string) => void;
    /** Shorthand helpers */
    toastError:   (message: string, title?: string) => void;
    toastWarning: (message: string, title?: string) => void;
    toastSuccess: (message: string, title?: string) => void;
    toastInfo:    (message: string, title?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<Toast[]>([]);
    const timersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

    const removeToast = useCallback((id: string) => {
        setToasts(prev => prev.filter(t => t.id !== id));
        clearTimeout(timersRef.current[id]);
        delete timersRef.current[id];
    }, []);

    const addToast = useCallback((toast: Omit<Toast, 'id'>) => {
        const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
        const duration = toast.duration ?? (toast.variant === 'error' ? 8000 : 4500);

        setToasts(prev => {
            // Deduplicate: if the exact same message is already visible, skip
            if (prev.some(t => t.message === toast.message && t.variant === toast.variant)) return prev;
            // Cap at 5 toasts — drop the oldest
            const next = [...prev, { ...toast, id, duration }];
            return next.length > 5 ? next.slice(next.length - 5) : next;
        });

        if (duration > 0) {
            timersRef.current[id] = setTimeout(() => removeToast(id), duration);
        }
    }, [removeToast]);

    const toastError   = useCallback((message: string, title?: string) => addToast({ variant: 'error',   message, title }), [addToast]);
    const toastWarning = useCallback((message: string, title?: string) => addToast({ variant: 'warning', message, title }), [addToast]);
    const toastSuccess = useCallback((message: string, title?: string) => addToast({ variant: 'success', message, title }), [addToast]);
    const toastInfo    = useCallback((message: string, title?: string) => addToast({ variant: 'info',    message, title }), [addToast]);

    return (
        <ToastContext.Provider value={{ toasts, addToast, removeToast, toastError, toastWarning, toastSuccess, toastInfo }}>
            {children}
        </ToastContext.Provider>
    );
}

export function useToast(): ToastContextValue {
    const ctx = useContext(ToastContext);
    if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
    return ctx;
}
