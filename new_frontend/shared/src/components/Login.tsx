import React, { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import { LogIn, Loader2, AlertCircle } from 'lucide-react';
import { cn } from '../utils/cn';
import { verifyOtpLogin, ApiError } from '../utils/api';
import OtpInputs from './OtpInputs';
import { useTranslation } from 'react-i18next';

export interface LoginProps {
    onLoginSuccess: (username: string) => void;
    initialError?: string | null;
    title?: string;
    subtitle?: string;
    appName?: string;
    icon?: React.ReactNode;
    onVerifyOtp?: (otp: string) => Promise<{ token: string; username: string }>;
    headerRightContent?: React.ReactNode;
}

export default function Login({
    onLoginSuccess,
    initialError,
    title,
    subtitle,
    appName,
    icon,
    onVerifyOtp = verifyOtpLogin,
    headerRightContent
}: LoginProps) {
    const { t } = useTranslation();
    const [otp, setOtp] = useState<string[]>(Array(6).fill(''));
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(initialError || null);
    const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

    useEffect(() => {
        if (initialError) {
            setError(initialError);
        }
    }, [initialError]);

    useEffect(() => {
        if (inputRefs.current[0]) {
            inputRefs.current[0].focus();
        }
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>, index: number) => {
        const value = e.target.value;
        if (isNaN(Number(value))) return;

        const newOtp = [...otp];
        newOtp[index] = value.substring(value.length - 1);
        setOtp(newOtp);

        if (value && index < 5 && inputRefs.current[index + 1]) {
            inputRefs.current[index + 1]?.focus();
        }
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>, index: number) => {
        if (e.key === 'Backspace') {
            if (!otp[index] && index > 0) {
                const newOtp = [...otp];
                newOtp[index - 1] = '';
                setOtp(newOtp);
                inputRefs.current[index - 1]?.focus();
            }
        } else if (e.key === 'ArrowLeft' && index > 0) {
            inputRefs.current[index - 1]?.focus();
            setTimeout(() => {
                if (inputRefs.current[index - 1]) {
                    inputRefs.current[index - 1]!.selectionStart = inputRefs.current[index - 1]!.value.length;
                    inputRefs.current[index - 1]!.selectionEnd = inputRefs.current[index - 1]!.value.length;
                }
            }, 0);
        } else if (e.key === 'ArrowRight' && index < 5) {
            inputRefs.current[index + 1]?.focus();
        }
    };

    const handlePaste = (e: React.ClipboardEvent) => {
        e.preventDefault();
        const pastedData = e.clipboardData.getData('text/plain').slice(0, 6).replace(/\D/g, '');
        if (pastedData) {
            const newOtp = [...otp];
            for (let i = 0; i < pastedData.length; i++) {
                if (i < 6) newOtp[i] = pastedData[i];
            }
            setOtp(newOtp);
            const focusIndex = Math.min(pastedData.length, 5);
            inputRefs.current[focusIndex]?.focus();
        }
    };

    const handleLogin = async (e?: React.FormEvent) => {
        if (e) e.preventDefault();

        const otpString = otp.join('');
        if (otpString.length !== 6) {
            setError(t('login.invalid_otp', 'Invalid one-time password. Please try again.'));
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const data = await onVerifyOtp(otpString);
            onLoginSuccess(data.username);
        } catch (err: unknown) {
            if (err instanceof ApiError) {
                if (err.status === 403) {
                    if (err.code === 'E_AUTH_INVALID') {
                        setError(t('app.invalid_auth', 'Invalid authentication'));
                    } else if (err.code === 'E_AUTH_EXPIRED' || err.code === 'E_AUTH_REVOKED') {
                        setError(t('app.logged_out_msg', "You've been logged out"));
                    } else {
                        setError(err.message);
                    }
                } else {
                    setError(err.message);
                }
            } else if (err instanceof Error) {
                setError(err.message);
            } else {
                setError(t('login.network_error', 'Network error, please check connections.'));
            }
        } finally {
            setLoading(false);
        }
    };

    const displayTitle = title || t('login.secure_access', 'Secure Access');
    const displaySubtitle = subtitle || t('login.subtitle', 'Please authenticate to access the system');

    return (
        <div className="flex min-h-[100dvh] flex-col items-center pt-[15vh] justify-start bg-gray-50 px-4 py-8 dark:bg-zinc-950 sm:px-6 lg:px-8 transition-colors duration-300 relative">
            {headerRightContent && (
                <div className="absolute top-6 right-6 flex items-center gap-3 z-20">
                    {headerRightContent}
                </div>
            )}

            <div className="w-full max-w-[32rem] space-y-8 rounded-2xl bg-white p-10 shadow-xl ring-1 ring-gray-900/5 dark:bg-zinc-900 dark:ring-white/10 relative overflow-hidden">
                {/* Subtle decorative background blob for dark mode */}
                <div className="absolute -top-[50%] -left-[50%] w-[200%] h-[200%] bg-gradient-to-br from-indigo-500/10 via-transparent to-transparent opacity-0 dark:opacity-100 pointer-events-none transition-opacity duration-300 rounded-full blur-3xl"></div>

                <div className="relative text-center">
                    {appName && (
                        <p className="text-xs font-semibold tracking-wider uppercase text-indigo-600 dark:text-indigo-400 mb-4">
                            {appName}
                        </p>
                    )}
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/30">
                        {icon || <LogIn className="h-8 w-8 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />}
                    </div>
                    <h2 className="mt-6 text-3xl font-extrabold tracking-tight text-gray-900 dark:text-white">
                        {displayTitle}
                    </h2>
                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                        {displaySubtitle}
                    </p>
                </div>

                <form className="mt-8 space-y-6 relative" onSubmit={handleLogin}>
                    <div className="flex flex-col items-center gap-6">
                        <div className="flex items-center justify-center gap-x-3" onPaste={handlePaste}>
                            <OtpInputs
                                startIndex={0}
                                endIndex={2}
                                otp={otp}
                                inputRefs={inputRefs}
                                handleChange={handleChange}
                                handleKeyDown={handleKeyDown}
                            />

                            <div className="flex justify-center items-center">
                                <span className="text-2xl font-bold leading-none select-none text-gray-400 dark:text-zinc-600">-</span>
                            </div>

                            <OtpInputs
                                startIndex={3}
                                endIndex={5}
                                otp={otp}
                                inputRefs={inputRefs}
                                handleChange={handleChange}
                                handleKeyDown={handleKeyDown}
                            />
                        </div>

                        {error && (
                            <div className="flex items-center gap-2 text-red-600 dark:text-red-400 text-sm font-medium animate-in fade-in slide-in-from-top-1 text-center">
                                <AlertCircle className="w-4 h-4 shrink-0" />
                                <span>{error}</span>
                            </div>
                        )}
                    </div>

                    <div>
                        <button
                            type="submit"
                            disabled={loading || otp.join('').length !== 6}
                            className={cn(
                                "group relative flex w-full justify-center rounded-xl border border-transparent py-4 px-4 text-sm font-semibold text-white transition-all duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 dark:focus:ring-offset-zinc-900 shadow-md cursor-pointer",
                                loading || otp.join('').length !== 6
                                    ? "bg-indigo-400 dark:bg-indigo-500/50 cursor-not-allowed opacity-80"
                                    : "bg-indigo-600 hover:bg-indigo-700 hover:shadow-lg hover:-translate-y-0.5 dark:bg-indigo-500 dark:hover:bg-indigo-400"
                            )}
                        >
                            {loading ? (
                                <span className="flex items-center gap-2">
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    {t('login.verifying', 'Verifying...')}
                                </span>
                            ) : (
                                t('login.verify_btn', 'Verify OTP')
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
