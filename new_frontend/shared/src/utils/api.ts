import type { AuthTokenResponse, User } from '../types/auth';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

let authToken = localStorage.getItem('authToken') || '';

export function getAuthToken(): string {
    return authToken;
}

export function setAuthToken(token: string) {
    authToken = token;
    if (token) {
        localStorage.setItem('authToken', token);
    } else {
        localStorage.removeItem('authToken');
    }
}

export function clearAuthToken() {
    setAuthToken('');
}

export class ApiError extends Error {
    status: number;
    code?: string;

    constructor(message: string, status: number, code?: string) {
        super(message);
        this.status = status;
        this.code = code;
        this.name = 'ApiError';
        Object.setPrototypeOf(this, ApiError.prototype);
    }
}

export async function getResponse(endpoint: string, options: RequestInit = {}): Promise<Response> {
    const url = `${API_BASE_URL}${endpoint}`;

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string> || {}),
    };

    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }

    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
        let errorMessage = 'An error occurred during verification.';
        let errorCode: string | undefined;
        try {
            const errorData = await response.json();
            if (errorData.message) errorMessage = errorData.message;
            if (errorData.detail?.code) {
                errorCode = errorData.detail.code;
            }
        } catch {
            if (response.statusText) errorMessage = response.statusText;
        }
        throw new ApiError(errorMessage, response.status, errorCode);
    }
    return response;
}

export async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const response = await getResponse(endpoint, options);
    return await response.json();
}

// --- Auth Endpoints ---

export async function verifyOtpLogin(otp: string): Promise<AuthTokenResponse> {
    const response = await apiRequest<AuthTokenResponse>('/auth/otp', {
        method: 'POST',
        body: JSON.stringify({
            purpose: 'login',
            duration: 120,
            otp: otp
        })
    });
    setAuthToken(response.token);
    return response;
}

export async function logout(): Promise<void> {
    try {
        await apiRequest('/auth/logout', { method: 'POST' });
    } finally {
        setAuthToken('');
    }
}

export async function getCurrentUser(): Promise<User | null> {
    try {
        return await apiRequest<User | null>('/users/get', { method: 'GET' });
    } catch (err) {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
            clearAuthToken();
            return null;
        }
        throw err;
    }
}

export async function checkOtpConfigured(): Promise<boolean> {
    try {
        const res = await apiRequest<{ property: string; value: boolean }>('/auth/otp/get/is_configured', {
            method: 'GET'
        });
        return !!res.value;
    } catch {
        return true;
    }
}
