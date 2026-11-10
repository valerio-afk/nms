import { useState, useEffect, useRef, useCallback } from 'react';
import { API_BASE_URL } from '@nms/shared';

export type ServerStatus = 'online' | 'offline' | 'reconnecting';

const POLL_INTERVAL_ONLINE = 10_000;  // check every 10 s when server is up
const POLL_INTERVAL_OFFLINE = 3_000;  // retry every 3 s when server is down

/**
 * Periodically probes the backend via GET /system/test and returns the
 * current reachability status.
 *
 * - 'online'       — last probe succeeded (or we just logged in)
 * - 'offline'      — probe failed with a network/timeout error
 * - 'reconnecting' — was offline, a new probe is in-flight
 *
 * @param isLoggedIn  Pass the app's login state so we can:
 *   1. Skip probing while on the login screen (the server is clearly reachable
 *      if the login page loaded).
 *   2. Immediately mark the server online when a fresh login is detected,
 *      so there is no banner flash right after logging in.
 */
export function useServerStatus(isLoggedIn: boolean): ServerStatus {
    const [status, setStatus] = useState<ServerStatus>('online');
    const statusRef = useRef<ServerStatus>('online');
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const clearTimer = useCallback(() => {
        if (timerRef.current) {
            clearTimeout(timerRef.current);
            timerRef.current = null;
        }
    }, []);

    const probe = useCallback(async () => {
        const wasOffline = statusRef.current === 'offline';
        if (wasOffline) {
            statusRef.current = 'reconnecting';
            setStatus('reconnecting');
        }

        try {
            const token = localStorage.getItem('authToken') ?? '';
            const headers: Record<string, string> = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            // /system/test is a minimal endpoint: validates the token and returns ()
            // 401/403 still means the server answered → it's reachable
            const res = await fetch(`${API_BASE_URL}/system/test`, {
                method: 'GET',
                headers,
                signal: AbortSignal.timeout(2_000),
            });

            if (res.ok || res.status === 401 || res.status === 403) {
                statusRef.current = 'online';
                setStatus('online');
            } else {
                throw new Error(`HTTP ${res.status}`);
            }
        } catch {
            statusRef.current = 'offline';
            setStatus('offline');
        }

        const interval = statusRef.current === 'offline' ? POLL_INTERVAL_OFFLINE : POLL_INTERVAL_ONLINE;
        timerRef.current = setTimeout(probe, interval);
    }, []);

    useEffect(() => {
        clearTimer();

        if (isLoggedIn) {
            // User just logged in — the login itself proves the server is up.
            // Reset to online immediately (no banner flash) and begin polling
            // only after a full interval.
            statusRef.current = 'online';
            setStatus('online');
            timerRef.current = setTimeout(probe, POLL_INTERVAL_ONLINE);
        } else {
            // On the login screen the server is obviously reachable, so stay
            // 'online' and don't poll at all.
            statusRef.current = 'online';
            setStatus('online');
        }

        return clearTimer;
    }, [isLoggedIn, probe, clearTimer]);

    return status;
}
