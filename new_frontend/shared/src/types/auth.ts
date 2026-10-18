export interface AuthTokenResponse {
    token: string;
    username: string;
    expire_date?: number;
}

export interface UserQuota {
    used: number;
    quota: number;
}

export interface User {
    username: string;
    visible_name?: string | null;
    permissions?: string[] | null;
    quota?: UserQuota | null;
    sudo: boolean;
    admin: boolean;
    first_login_token?: string | null;
    home_dir?: string | null;
    uid?: number | null;
    gid?: number | null;
    notifications: number;
}

export const UserPermissions = {
    ClientDashboardAccess: 'client.dashboard.access',
    ClientDashboardDisks: 'client.dashboard.disks',
    ClientDashboardNetworks: 'client.dashboard.networks',
    ClientDashboardServices: 'client.dashboard.services',
    ClientDashboardUsers: 'client.dashboard.users',
    ClientDashboardAdvanced: 'client.dashboard.advanced',
    PoolDisksHealth: 'pool.disks.health',
    PoolDisksFormat: 'pool.disks.format',
    PoolDisksReplace: 'pool.disks.replace',
    PoolToolsVerify: 'pool.tools.verify',
    PoolToolsMount: 'pool.tools.mount',
    PoolToolsRecovery: 'pool.tools.recovery',
    PoolToolsSnapshot: 'pool.tools.snapshot',
    PoolConfCreate: 'pool.conf.create',
    PoolConfImport: 'pool.conf.import',
    PoolConfExpand: 'pool.conf.expand',
} as const;

export type UserPermission = typeof UserPermissions[keyof typeof UserPermissions];
