export function formatBytes (bytes: number | undefined): string {
    if (bytes === undefined || bytes === null) return '--';
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export function formatDate (timestamp: number): string {
    // Assuming timestamp is in seconds, convert to ms
    const date = new Date(timestamp * 1000);
    return new Intl.DateTimeFormat(navigator.language, {
        dateStyle: 'medium',
        timeStyle: 'short'
    }).format(date);
};