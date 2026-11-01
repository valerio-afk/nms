export function formatBytes(bytes: number, decimals: number = 2): string {
    if (bytes === 0) return '0 B';
    if (!bytes || isNaN(bytes)) return '0 B';

    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];

    const i = Math.floor(Math.log(bytes) / Math.log(k));
    const index = Math.min(i, sizes.length - 1);

    return `${parseFloat((bytes / Math.pow(k, index)).toFixed(dm))} ${sizes[index]}`;
}

export function formatUptime(seconds?: number): string {
    if (!seconds || seconds <= 0) return '0m';

    // If seconds is a Unix epoch boot timestamp (> 1e9), calculate elapsed seconds
    let elapsed = seconds;
    if (seconds > 1_000_000_000) {
        elapsed = Math.max(0, Math.floor(Date.now() / 1000) - seconds);
    }

    const days = Math.floor(elapsed / (3600 * 24));
    const hours = Math.floor((elapsed % (3600 * 24)) / 3600);
    const minutes = Math.floor((elapsed % 3600) / 60);

    const parts: string[] = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0 || parts.length === 0) parts.push(`${minutes}m`);

    return parts.join(' ');
}

export function formatBootDate(seconds?: number, lang?: string): string | null {
    if (!seconds || seconds <= 1_000_000_000) return null;
    const date = new Date(seconds * 1000);
    try {
        return date.toLocaleDateString(lang === 'it' ? 'it-IT' : 'en-US', {
            weekday: 'short',
            day: 'numeric',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return date.toLocaleString();
    }
}

export function formatPercent(used: number, total: number): number {
    if (!total || total <= 0) return 0;
    const pct = (used / total) * 100;
    return Math.min(Math.max(parseFloat(pct.toFixed(1)), 0), 100);
}
