use strum::{EnumString,Display,EnumIter,IntoEnumIterator};

#[derive(Display,EnumString,EnumIter)]
pub enum UserPermissions
{

    #[strum(to_string="client.dashboard.access")]
    ClientDashboardAccess,

    #[strum(to_string="client.dashboard.disks")]
    ClientDashboardDisks,

    #[strum(to_string="client.dashboard.networks")]
    ClientDashboardNetworks,

    #[strum(to_string="client.dashboard.services")]
    ClientDashboardServices,

    #[strum(to_string="client.dashboard.users")]
    ClientDashboardUsers,

    #[strum(to_string="client.dashboard.advanced")]
    ClientDashboardAdvanced,

    #[strum(to_string="pool.disks.health")]
    PoolDisksHealth,

    #[strum(to_string="pool.disks.format")]
    PoolDisksFormat,

    #[strum(to_string="pool.disks.replace")]
    PoolDisksReplace,

    #[strum(to_string="pool.tools.verify")]
    PoolToolsVerify,

    #[strum(to_string="pool.tools.mount")]
    PoolToolsMount,

    #[strum(to_string="pool.tools.recovery")]
    PoolToolsRecovery,

    #[strum(to_string="pool.tools.snapshot")]
    PoolToolsSnapshot,

    #[strum(to_string="pool.conf.create")]
    PoolConfCreate,

    #[strum(to_string="pool.conf.import")]
    PoolConfImport,

    #[strum(to_string="pool.conf.expand")]
    PoolConfExpand,

    #[strum(to_string="pool.conf.destroy")]
    PoolConfDestroy,

    #[strum(to_string="pool.conf.format")]
    PoolConfFormat,

    #[strum(to_string="pool.conf.get_info")]
    PoolConfGetInfo,

    #[strum(to_string="network.interface.manage")]
    NetworkIfaceManage,

    #[strum(to_string="network.ddns.manage")]
    NetworkDdnsManage,

    #[strum(to_string="network.vpn.manage")]
    NetworkVpnManage,

    #[strum(to_string="services.ssh.access")]
    ServicesSshAccess,

    #[strum(to_string="services.ssh.manage")]
    ServicesSshManage,

    #[strum(to_string="services.ftp.access")]
    ServicesFtpAccess,

    #[strum(to_string="services.ftp.manage")]
    ServicesFtpManage,

    #[strum(to_string="services.nfs.manage")]
    ServicesNfsManage,

    #[strum(to_string="services.smb.access")]
    ServicesSmbAccess,

    #[strum(to_string="services.smb.manage")]
    ServicesSmbManage,

    #[strum(to_string="services.web.access")]
    ServicesWebAccess,

    #[strum(to_string="services.web.manage")]
    ServicesWebManage,

    #[strum(to_string="services.mediaserver.manage")]
    ServicesMediaserverManage,

    #[strum(to_string="sys.admin.acpi")]
    SysAdminAcpi,

    #[strum(to_string="sys.admin.events")]
    SysAdminEvents,

    #[strum(to_string="sys.admin.updates")]
    SysAdminUpdates,

    #[strum(to_string="sys.admin.systemctl")]
    SysAdminSystemctl,

    #[strum(to_string="sys.admin.logs")]
    SysAdminLogs,

    #[strum(to_string="users.account.manage")]
    UsersAccountManage,
}



impl UserPermissions
{
    pub fn is_allowed<T>(self:&Self,p:T) -> bool
    where T: AsRef<str>
    {       
        if p.as_ref() == "*" { return true; }
        
        let needle = self.to_string();
        let parts:Vec<&str> = needle.split(".").collect();
       

        for i in (1..=parts.len()).rev()
        {
            let mut candidate = parts[0..i].join(".");
            if candidate == p.as_ref() { return true; }


            candidate.push_str(".*");

            if candidate == p.as_ref() { return true; }
        }

        return false;
    }

    pub fn is_any_allowed<T>(self:&Self,p:&[T]) -> bool
    where T: AsRef<str>
    {
        return p.iter().any(|x| self.is_allowed(x));
    }
}


pub fn is_admin<T>(perm:&[T]) -> bool
where T: AsRef<str>
{
    if perm.iter().any(|x| x.as_ref() == "*") {return true;}

    let mut iter = UserPermissions::iter();

    iter.all(|x:UserPermissions| x.is_any_allowed(perm) )
}

mod test
{
    #[allow(unused)]
    use super::*;
    #[test]
    fn permissions_test()
    {
        assert!(UserPermissions::ClientDashboardAccess.is_allowed("client.dashboard.access"));
        assert!(UserPermissions::PoolDisksReplace.is_allowed("pool.disks.*"));
        assert!(UserPermissions::SysAdminLogs.is_allowed("sys.*"));
        assert!(UserPermissions::PoolDisksReplace.is_allowed("pool.disks"));
        assert!(UserPermissions::SysAdminLogs.is_allowed("sys"));
        assert!(UserPermissions::UsersAccountManage.is_allowed("*"));
        assert!(!UserPermissions::NetworkDdnsManage.is_allowed("network.vpn.manage"));
        assert!(!UserPermissions::NetworkVpnManage.is_allowed("services.ftp.manage"));
        assert!(!UserPermissions::ServicesWebManage.is_allowed("abracadabra"));

        assert!(UserPermissions::from_str("client.dashboard.access").unwrap().is_allowed("client.dashboard.access"));
        assert!(UserPermissions::from_str("pool.disks.replace").unwrap().is_allowed("pool.disks.*"));
        assert!(UserPermissions::from_str("sys.admin.logs").unwrap().is_allowed("sys.*"));
        assert!(UserPermissions::from_str("pool.disks.replace").unwrap().is_allowed("pool.disks"));
        assert!(UserPermissions::from_str("sys.admin.logs").unwrap().is_allowed("sys"));
        assert!(UserPermissions::from_str("users.account.manage").unwrap().is_allowed("*"));
        assert!(!UserPermissions::from_str("network.ddns.manage").unwrap().is_allowed("network.vpn.manage"));
        assert!(!UserPermissions::from_str("network.vpn.manage").unwrap().is_allowed("services.ftp.manage"));
        assert!(!UserPermissions::from_str("services.web.manage").unwrap().is_allowed("abracadabra"));

        assert!(is_admin(&[
            "*"
        ]));

        assert!(is_admin(&[
            "client.*",
            "pool.*",
            "network.*",
            "services.*",
            "sys.*",
            "users.*"
        ]));

        assert!(is_admin(&[
            "client.dashboard.*",
            "pool.disks.*",
            "pool.tools.*",
            "pool.conf.*",
            "network.interface.*",
            "network.ddns.*",
            "network.vpn.*",
            "services.ssh.*",
            "services.ftp.*",
            "services.nfs.*",
            "services.smb.*",
            "services.web.*",
            "services.mediaserver.*",
            "sys.admin.*",
            "users.account.*"
        ]));

        assert!(is_admin(&[
            "client.dashboard.access",
            "client.dashboard.disks",
            "client.dashboard.networks",
            "client.dashboard.services",
            "client.dashboard.users",
            "client.dashboard.advanced",
            "pool.disks.health",
            "pool.disks.format",
            "pool.disks.replace",
            "pool.tools.verify",
            "pool.tools.mount",
            "pool.tools.recovery",
            "pool.tools.snapshot",
            "pool.conf.create",
            "pool.conf.import",
            "pool.conf.expand",
            "pool.conf.destroy",
            "pool.conf.format",
            "pool.conf.get_info",
            "network.interface.manage",
            "network.ddns.manage",
            "network.vpn.manage",
            "services.ssh.access",
            "services.ssh.manage",
            "services.ftp.access",
            "services.ftp.manage",
            "services.nfs.manage",
            "services.smb.access",
            "services.smb.manage",
            "services.web.access",
            "services.web.manage",
            "services.mediaserver.manage",
            "sys.admin.acpi",
            "sys.admin.events",
            "sys.admin.updates",
            "sys.admin.systemctl",
            "sys.admin.logs",
            "users.account.manage",
        ]));

        assert!(!is_admin(&[
            "pool.*",
            "network.*",
            "services.*",
            "sys.*",
            "users.*"
        ]));

        assert!(!is_admin(&[
            "client.dashboard.*",
            "pool.disks.*",
            "pool.tools.*",
            "pool.conf.*",
            "network.interface.*",
            "network.ddns.*",
            "services.ssh.*",
            "services.ftp.*",
            "services.nfs.*",
            "services.smb.*",
            "services.web.*",
            "services.mediaserver.*",
            "sys.admin.*",
            "users.account.*"
        ]));

        assert!(!is_admin(&[
            "client.dashboard.access",
            "client.dashboard.disks",
            "client.dashboard.networks",
            "client.dashboard.services",
            "client.dashboard.users",
            "client.dashboard.advanced",
            "pool.disks.health",
            "pool.disks.format",
            "pool.disks.replace",
            "pool.tools.verify",
            "pool.tools.mount",
            "pool.tools.recovery",
            "pool.tools.snapshot",
            "pool.conf.create",
            "pool.conf.import",
            "pool.conf.expand",
            "pool.conf.destroy",
            "pool.conf.format",
            "pool.conf.get_info",
            "network.interface.manage",
            "network.ddns.manage",
            "network.vpn.manage",
            "services.ssh.access",
            "services.ssh.manage",
            "services.ftp.access",
            "services.ftp.manage",
            "services.nfs.manage",
            "services.smb.access",
            "services.smb.manage",
            "services.web.access",
            "services.web.manage",
            "services.mediaserver.manage",
            "sys.admin.events",
            "sys.admin.updates",
            "sys.admin.systemctl",
            "sys.admin.logs",
            "users.account.manage",
        ]));
    }
}

