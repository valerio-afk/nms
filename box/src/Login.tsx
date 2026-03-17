import React, { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import { LogIn, Loader2, AlertCircle } from 'lucide-react';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';
import { verifyOtpLogin, ApiError } from './utils/api';
import OtpInputs from './components/OtpInputs';

// Utility for neat tailwind class merging if needed
function cn(...inputs: (string | undefined | null | false)[]) {
    return twMerge(clsx(inputs));
}

interface LoginProps {
    onLoginSuccess: (username: string) => void;
    initialError?: string | null;
}

export default function Login({ onLoginSuccess, initialError }: LoginProps) {
    const [otp, setOtp] = useState<string[]>(Array(6).fill(''));
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(initialError || null);
    const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

    // If initialError changes, update the local error state
    useEffect(() => {
        if (initialError) {
            setError(initialError);
        }
    }, [initialError]);

    // Focus the first input on mount
    useEffect(() => {
        if (inputRefs.current[0]) {
            inputRefs.current[0].focus();
        }
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>, index: number) => {
        const value = e.target.value;

        // Allow only numbers
        if (isNaN(Number(value))) return;

        const newOtp = [...otp];
        // Keep only the last character entered
        newOtp[index] = value.substring(value.length - 1);
        setOtp(newOtp);

        // Jump to next if filled
        if (value && index < 5 && inputRefs.current[index + 1]) {
            inputRefs.current[index + 1]?.focus();
        }
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>, index: number) => {
        if (e.key === 'Backspace') {
            if (!otp[index] && index > 0) {
                // If current is empty, jump to previous and clear it
                const newOtp = [...otp];
                newOtp[index - 1] = '';
                setOtp(newOtp);
                inputRefs.current[index - 1]?.focus();
            }
        } else if (e.key === 'ArrowLeft' && index > 0) {
            inputRefs.current[index - 1]?.focus();
            // small delay to position cursor at the end
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
            // Focus the next empty input or the last one
            const focusIndex = Math.min(pastedData.length, 5);
            inputRefs.current[focusIndex]?.focus();
        }
    };

    const handleLogin = async (e?: React.FormEvent) => {
        if (e) e.preventDefault();

        const otpString = otp.join('');
        if (otpString.length !== 6) {
            setError('Please enter all 6 digits.');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const data = await verifyOtpLogin(otpString);

            // Success
            onLoginSuccess(data.username);
        } catch (err: unknown) {
            if (err instanceof ApiError) {
                if (err.status === 403) {
                    if (err.code === 'E_AUTH_INVALID') {
                        setError('Invalid authentication');
                    } else if (err.code === 'E_AUTH_EXPIRED' || err.code === 'E_AUTH_REVOKED') {
                        setError("You've been logged out");
                    } else {
                        setError(err.message);
                    }
                } else {
                    setError(err.message);
                }
            } else if (err instanceof Error) {
                setError(err.message);
            } else {
                setError('An error occurred during verification.');
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex min-h-[100dvh] items-start pt-[20vh] justify-center bg-gray-50 px-4 py-12 dark:bg-zinc-950 sm:px-6 lg:px-8 transition-colors duration-300">
            <div className="w-full max-w-[32rem] space-y-8 rounded-2xl bg-white p-10 shadow-xl ring-1 ring-gray-900/5 dark:bg-zinc-900 dark:ring-white/10 relative overflow-hidden">

                {/* Subtle decorative background blob for dark mode, hidden in light mode for cleaner look */}
                <div className="absolute -top-[50%] -left-[50%] w-[200%] h-[200%] bg-gradient-to-br from-indigo-500/10 via-transparent to-transparent opacity-0 dark:opacity-100 pointer-events-none transition-opacity duration-300 rounded-full blur-3xl"></div>

                <div className="relative">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/30">
                        <LogIn className="h-8 w-8 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
                    </div>
                    <h2 className="mt-6 text-center text-3xl font-extrabold tracking-tight text-gray-900 dark:text-white">
                        Secure Login
                    </h2>
                    <p className="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">
                        Enter the 6-digit one-time password to access your Box.
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
                                <span className="text-2xl font-bold leading-none select-none">-</span>
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
                            <div className="flex items-center gap-2 text-red-600 dark:text-red-400 text-sm font-medium animate-in fade-in slide-in-from-top-1">
                                <AlertCircle className="w-4 h-4" />
                                <span>{error}</span>
                            </div>
                        )}

                    </div>

                    <div>
                        <button
                            type="submit"
                            disabled={loading || otp.join('').length !== 6}
                            className={cn(
                                "group relative flex w-full justify-center rounded-xl border border-transparent py-4 px-4 text-sm font-semibold text-white transition-all duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2  focus:ring-indigo-500 dark:focus:ring-offset-zinc-900 shadow-md",
                                loading || otp.join('').length !== 6
                                    ? "bg-indigo-400 dark:bg-indigo-500/50 cursor-not-allowed opacity-80"
                                    : "bg-indigo-600 hover:bg-indigo-700 hover:shadow-lg hover:-translate-y-0.5 dark:bg-indigo-500 dark:hover:bg-indigo-400"
                            )}
                        >
                            {loading ? (
                                <span className="flex items-center gap-2">
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    Verifying...
                                </span>
                            ) : (
                                "Login"
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
