import type { AuthTokenResponse, User } from '../types/auth';
import { getErrorMessage, type ErrorDetail } from './errors';

export const API_BASE_URL = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) || '/api/v1';

let authToken = (typeof localStorage !== 'undefined' ? localStorage.getItem('authToken') : '') || '';

export function getAuthToken(): string {
    return authToken;
}

export function setAuthToken(token: string) {
    authToken = token;
    if (typeof localStorage !== 'undefined') {
        if (token) {
            localStorage.setItem('authToken', token);
        } else {
            localStorage.removeItem('authToken');
        }
    }
}

export function clearAuthToken() {
    setAuthToken('');
}

export class ApiError extends Error {
    status: number;
    code?: string;
    params?: (string | number)[] | Record<string, any> | null;
    detail?: ErrorDetail;

    constructor(
        message: string,
        status: number,
        code?: string,
        params?: (string | number)[] | Record<string, any> | null,
        detail?: ErrorDetail
    ) {
        super(message);
        this.status = status;
        this.code = code;
        this.params = params;
        this.detail = detail;
        this.name = 'ApiError';
        Object.setPrototypeOf(this, ApiError.prototype);
    }

    getLocalizedMessage(lang?: string): string {
        if (this.code) {
            return getErrorMessage(this.code, this.params, lang);
        }
        return this.message;
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
        let errorParams: (string | number)[] | Record<string, any> | null = null;
        let errorDetail: ErrorDetail | undefined;

        try {
            const errorData = await response.json();
            if (errorData.detail) {
                errorDetail = errorData.detail;
                if (typeof errorData.detail === 'object') {
                    if (errorData.detail.code) {
                        errorCode = errorData.detail.code;
                    }
                    if (errorData.detail.params !== undefined) {
                        errorParams = errorData.detail.params;
                    }
                }
            } else if (errorData.code) {
                errorCode = errorData.code;
                errorParams = errorData.params ?? null;
            }

            if (errorCode) {
                errorMessage = getErrorMessage(errorCode, errorParams);
            } else if (errorData.message) {
                errorMessage = errorData.message;
            }
        } catch {
            if (response.statusText) errorMessage = response.statusText;
        }

        throw new ApiError(errorMessage, response.status, errorCode, errorParams, errorDetail);
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
