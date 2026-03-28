// Use environment variable for API URL in the future, for now hardcode based on requirement
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

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


async function getResponse(endpoint: string, options: RequestInit = {}): Promise<Response> {
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
    return response;
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const response = await getResponse(endpoint, options);
    return await response.json();
}


// --- Auth Endpoints ---

export async function verifyOtpLogin(otp: string): Promise<{ token: string, username: string }> {
    const response = await apiRequest<{ token: string, username: string }>('/auth/otp', {
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
    used: number;
    quota: number;
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

export async function cpFs(src: string, dst: string): Promise<void> {
    await apiRequest('/fs/cp', {
        method: 'POST',
        body: JSON.stringify({
            src: src,
            dst: dst
        })
    });
}

export async function rmFs(path: string): Promise<void> {
    await apiRequest(`/fs/item/${path}`, {
        method: 'DELETE'
    });
}

export async function zipFs(targetPath: string, files: string[], format: "zip" | "gz" | "xz" | "bz2" | "7z" = "zip"): Promise<void> {
    // Assuming backend endpoint is /fs/zip to match typical routing. If it's literally /zip, we route it.
    await apiRequest('/fs/zip', {
        method: 'POST',
        body: JSON.stringify({
            zip_filename: targetPath,
            files: files,
            format: format
        })
    });
}

export async function unzipFs(path: string): Promise<void> {
    await apiRequest(`/fs/unzip/${path}`, {
        method: 'POST'
    });
}

export async function getQuota(): Promise<UserQuota> {
    return await apiRequest<UserQuota>('/fs/quota', { method: 'GET' });
}

export async function getChecksum(path: string): Promise<string> {
    return await apiRequest<string>(`/fs/checksum/${path}`, { method: 'GET' });
}

export async function getPreviewToken(path: string): Promise<string> {
    const endpoint = `/fs/preview/${path}`;
    const url = `${API_BASE_URL}${endpoint}`;

    const token = localStorage.getItem('authToken') || '';
    const headers: Record<string, string> = {};
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(url, { method: 'HEAD', headers });

    if (!response.ok) {
        throw new Error('Failed to fetch preview token');
    }

    return response.headers.get('x-preview-token') || '';
}

export function getPreviewUrl(path: string, previewToken: string): string {
    const endpoint = `/fs/preview/${path}`;
    const url = `${API_BASE_URL}${endpoint}`;
    if (previewToken) {
        return `${url}?token=${encodeURIComponent(previewToken)}`;
    }
    return url;
}

export async function downloadFile(path: string): Promise<void> {
    const response = await getResponse(`/fs/item/${path}`, {
        method: 'GET'
    });

    const disposition = response.headers.get("Content-Disposition");
    let filename = "download";

    if (disposition && disposition.includes("filename=")) {
        filename = disposition
            .split("filename=")[1]
            .replace(/"/g, "");
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();

    window.URL.revokeObjectURL(url);
}