// Use environment variable for API URL in the future, for now hardcode based on requirement
export const API_BASE_URL = 'http://192.168.1.180/api/v1';

let authToken = localStorage.getItem('authToken') || '';

export function setAuthToken(token: string) {
    authToken = token;
    if (token) {
        localStorage.setItem('authToken', token);
    } else {
        localStorage.removeItem('authToken');
    }
}

export class ApiError extends Error {
    status: number;
    code?: string;

    constructor(
        message: string,
        status: number,
        code?: string
    ) {
        super(message);
        this.status = status;
        this.code = code;
        this.name = 'ApiError';
        // Set prototype to maintain instanceof check
        Object.setPrototypeOf(this, ApiError.prototype);
    }
}

/**
 * Helper to make API requests with standardized error handling
 */
async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
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
        // Attempt to parse error message from backend if possible
        let errorMessage = 'An error occurred during verification.';
        let errorCode: string | undefined;
        try {
            const errorData = await response.json();
            if (errorData.message) errorMessage = errorData.message;
            if (errorData.detail?.code) {
                errorCode = errorData.detail.code;
            }
        } catch {
            // If parsing fails, use fallback or status text
            if (response.statusText) errorMessage = response.statusText;
        }
        throw new ApiError(errorMessage, response.status, errorCode);
    }

    // Handle case where successful response might not be JSON
    try {
        return await response.json();
    } catch {
        return {} as T; // Return empty object if json parsing fails on success
    }
}

// --- Auth Endpoints ---

export async function verifyOtpLogin(otp: string): Promise<{ token: string, username: string }> {
    const response = await apiRequest<{ token: string, username: string }>('/auth/otp/verify', {
        method: 'POST',
        body: JSON.stringify({
            purpose: 'login',
            duration: 120,
            "otp": otp
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

// Add more API calls here sequentially

export interface FileInfo {
    type: "dir" | "image" | "video" | "audio" | "text" | "zip" | "bin" | "pdf" | "unk";
    name: string;
    size?: number;
    creation_time: number;
    real: boolean;
}

export interface FSBrowse {
    path: string;
    files: FileInfo[];
}

export interface UserQuota {
    used:number;
    quota:number;
}

export async function browseFs(path: string = ""): Promise<FSBrowse> {
    const endpoint = path ? `/fs/browse/${path}` : '/fs/browse';
    return await apiRequest<FSBrowse>(endpoint, { method: 'GET' });
}

export async function mkdirFs(currentPath: string, newDir: string): Promise<void> {
    await apiRequest('/fs/mkdir', {
        method: 'POST',
        body: JSON.stringify({
            path: currentPath,
            new_dir: newDir
        })
    });
}

export async function mvFs(oldPath: string, newPath: string): Promise<void> {
    await apiRequest('/fs/mv', {
        method: 'POST',
        body: JSON.stringify({
            old_path: oldPath,
            new_path: newPath
        })
    });
}

export async function rmFs(path: string): Promise<void> {
    await apiRequest(`/fs/delete/${path}`, {
        method: 'GET'
    });
}

export async function getQuota(): Promise<UserQuota> {
    return await apiRequest<UserQuota>('/fs/quota', { method: 'GET' });
}
