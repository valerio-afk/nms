export {
    API_BASE_URL,
    getAuthToken,
    setAuthToken,
    clearAuthToken,
    ApiError,
    verifyOtpLogin,
    logout,
    getCurrentUser,
    checkOtpConfigured,
    getErrorMessage,
    formatErrorMessage,
    ERROR_MESSAGES_EN,
    ERROR_MESSAGES_IT,
    type ErrorDetail,
} from '@nms/shared';
import { apiRequest, getResponse, API_BASE_URL } from '@nms/shared';
export { apiRequest, getResponse };

// Add more API calls here sequentially

export interface FileSharedInfo {
    expire_date: number | null;
    share_with: Record<string, { can_edit: boolean }> | null;
}

export interface FileInfo {
    type: "dir" | "image" | "video" | "audio" | "text" | "zip" | "bin" | "pdf" | "word" | "spreadsheet" | "presentation" | "unk";
    name: string;
    size?: number;
    creation_time: number;
    real: boolean;
    shared?: FileSharedInfo | null;
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

export async function downloadFile(path: string, shareToken?: string): Promise<void> {
    const query = shareToken ? `?share_token=${encodeURIComponent(shareToken)}` : '';
    const response = await getResponse(`/fs/item/${path}${query}`, {
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

export async function getOnlyOfficeConfig(path: string, shareToken?: string): Promise<any> {
    const query = shareToken ? `?share_token=${encodeURIComponent(shareToken)}` : '';
    return await apiRequest<any>(`/fs/onlyoffice/${path}${query}`, { method: 'GET' });
}

export async function getOnlyOfficeConfigShared(path: string, shareToken: string): Promise<any> {
    return await apiRequest<any>(`/filesharing/onlyoffice/${path}?token=${encodeURIComponent(shareToken)}`, { method: 'GET' });
}

export interface SharingPermissions {
    username: string;
    can_edit: boolean;
}

export interface FileSharingPayload {
    path: string;
    sharing_permissions?: SharingPermissions[] | null;
    expire?: number | null;
}

export interface FileSharingResponse {
    token: string;
}

export async function shareFs(payload: FileSharingPayload): Promise<FileSharingResponse> {
    return await apiRequest<FileSharingResponse>('/fs/share', {
        method: 'POST',
        body: JSON.stringify(payload)
    });
}

export async function revokeShare(path: string): Promise<void> {
    await apiRequest(`/fs/share/${path}`, {
        method: 'DELETE'
    });
}

export async function getAllUsers(): Promise<string[]> {
    const data = await apiRequest<any[]>('/users/get/all', { method: 'GET' });
    return data.map(item => {
        if (typeof item === 'string') {
            return item;
        } else if (item && typeof item === 'object' && typeof item.username === 'string') {
            return item.username;
        }
        return '';
    }).filter(Boolean);
}

export interface SharedFileInfo extends FileInfo {
    can_edit: boolean;
    relative_path: string;
}

export async function getSharedFiles(): Promise<SharedFileInfo[]> {
    return await apiRequest<SharedFileInfo[]>('/fs/shared', {
        method: 'GET'
    });
}

export async function browseSharedFs(path: string): Promise<FSBrowse> {
    const endpoint = `/fs/shared/${path}`;
    return await apiRequest<FSBrowse>(endpoint, { method: 'GET' });
}

export async function browseFileSharing(shareToken: string, path?: string): Promise<SharedFileInfo[]> {
    const subpath = path ? `/${path}` : '';
    return await apiRequest<SharedFileInfo[]>(`/filesharing/browse${subpath}?token=${encodeURIComponent(shareToken)}`, {
        method: 'GET'
    });
}