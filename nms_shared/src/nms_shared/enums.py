from enum import Enum

class DiskStatus(Enum):
    NEW       = 0
    ONLINE    = 1
    OFFLINE   = -1
    CORRUPTED = -2

class LogFilter(Enum):
    FRONTEND = 'frontend'
    BACKEND = 'backend'
    WEB_SERVER = 'nginx'

class RequestMethod(Enum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"

class UserPermissions(Enum):
    CLIENT_DASHBOARD_ACCESS = "client.dashboard.access"
    CLIENT_DASHBOARD_DISKS = "client.dashboard.disks"
    CLIENT_DASHBOARD_NETWORKS = "client.dashboard.networks"
    CLIENT_DASHBOARD_SERVICES = "client.dashboard.services"
    CLIENT_DASHBOARD_USERS = "client.dashboard.users"
    CLIENT_DASHBOARD_ADVANCED = "client.dashboard.advanced"

    POOL_DISKS_HEALTH = "pool.disks.health"
    POOL_DISKS_FORMAT = "pool.disks.format"
    POOL_DISKS_REPLACE = "pool.disks.replace"
    POOL_TOOLS_VERIFY = "pool.tools.verify"
    POOL_TOOLS_MOUNT = "pool.tools.mount"
    POOL_TOOLS_RECOVERY = "pool.tools.recovery"
    POOL_TOOLS_SNAPSHOT = "pool.tools.snapshot"
    POOL_CONF_CREATE = "pool.conf.create"
    POOL_CONF_IMPORT = "pool.conf.import"
    POOL_CONF_EXPAND = "pool.conf.expand"
    POOL_CONF_DESTROY = "pool.conf.destroy"
    POOL_CONF_FORMAT = "pool.conf.format"
    POOL_CONF_GET_INFO = "pool.conf.get_info"

    NETWORK_IFACE_MANAGE = "network.interface.manage"
    NETWORK_DDNS_MANAGE = "network.ddns.manage"
    NETWORK_VPN_MANAGE = "network.vpn.manage"

    SERVICES_SSH_ACCESS = "services.ssh.access"
    SERVICES_SSH_MANAGE = "services.ssh.manage"
    SERVICES_FTP_ACCESS = "services.ftp.access"
    SERVICES_FTP_MANAGE = "services.ftp.manage"
    # SERVICES_NFS_ACCESS = "services.nfs.access"
    SERVICES_NFS_MANAGE = "services.nfs.manage"
    SERVICES_SMB_ACCESS = "services.smb.access"
    SERVICES_SMB_MANAGE = "services.smb.manage"
    SERVICES_WEB_ACCESS = "services.web.access"
    SERVICES_WEB_MANAGE = "services.web.manage"

    SYS_ADMIN_ACPI = "sys.admin.acpi"
    SYS_ADMIN_UPDATES = "sys.admin.updates"
    SYS_ADMIN_SYSTEMCTL = "sys.admin.systemctl"
    SYS_ADMIN_LOGS = "sys.admin.logs"

    USERS_ACCOUNT_MANAGE = "users.account.manage"


