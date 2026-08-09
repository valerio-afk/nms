use async_trait::async_trait;
use crate::backend::permissions::UserPermissions;
use crate::backend::remote_access::{ServiceAuth, ServiceError, ServicePermissionHooks, ServiceProperties, ServiceProperty, SystemdService};
use crate::cmdl::coreutils::{Cat, MV, Touch, Chmod, FileSystemPermissions, Stat, Tee};
use crate::cmdl::grep::{Grep,GrepFlags};
use crate::cmdl::sed::{Sed, SedFlags};
use crate::cmdl::{CmdConfig, CommandLine, Executable, Transaction};
use serde_json::{Number, Value};
use std::collections::HashMap;
use std::env::temp_dir;
use std::fs::File;
use std::io::{Write};
use std::ops::{Deref, DerefMut};
use std::path::PathBuf;
use anyhow::Error;
use crate::backend::utils::{detect_distro_family, DistroFamily};
use super::RemoteService;
use std::sync::LazyLock;
use crate::cmdl::firewall::{Firewall, FirewallAction, FirewallPort};
use crate::cmdl::selinux::{Protocol, SeLinuxSetBool};

static VSFTPD_CONF:LazyLock<HashMap<&'static str,&'static str>> = LazyLock::new(||{
    HashMap::from([
        ("anonymous_enable","NO"),
        ("local_enable", "YES"),
        ("write_enable", "YES"),
        ("ftpd_banner", "Welcome to NMS FTP Service."),
        ("chroot_local_user","NO"),
        ("userlist_enable", "YES"),
        ("userlist_file", ""),
        ("userlist_deny", "NO"),
        ("chroot_list_enable","NO"),
        ("pasv_min_port", ""),
        ("pasv_max_port", ""),
        ("pasv_enable", "YES"),
    ])
});

pub struct FTPService
{
    ftp_service: Box<SystemdService>,
    userlist_file: PathBuf
}

impl Deref for FTPService
{
    type Target = SystemdService;
    fn deref(&self) -> &Self::Target
    {
        &self.ftp_service
    }
}

impl DerefMut for FTPService
{
    fn deref_mut(&mut self) -> &mut Self::Target
    {
        &mut self.ftp_service
    }
}

#[async_trait]
impl ServicePermissionHooks for FTPService
{

    async fn permission_granted(&self, username:&str)
    {
        let _ = self.touch_userlist_file().await;

        let userlist_fname = self.userlist_file.to_str().unwrap();

        let grep = Grep(
            Some(vec![GrepFlags::Quiet,GrepFlags::WholeLine,GrepFlags::FixedString]),
            &username,
            Some(userlist_fname),
            CmdConfig::default()
        ).run().await;

        if let Ok(Some(o)) = grep && (o.exit_code==0) // this means the user already is granted
        {
            return;
        }

        let _ = Tee(
            userlist_fname,
            true,
            CmdConfig::default_with_stdin(format!("{username}\n").as_bytes().to_vec())
        ).run().await;

    }

    async fn permission_revoked(&self, username: &str)
    {
        let _ = Sed(Some(vec![SedFlags::InPlace]),
                    format!("/^{username}$/d"),
                    self.userlist_file.to_str(),
                    CmdConfig::default()
        ).run().await;
    }

    async fn user_deleted(&self, username: &str)
    {
        self.permission_revoked(username).await;
    }

}
#[async_trait]
impl ServiceProperties for FTPService
{
    fn properties(&self) -> Vec<ServiceProperty>
    {
        vec![ServiceProperty::PortRange]
    }

    async fn get_property(&mut self, prop: ServiceProperty) -> Result<&Value, ServiceError>
    {
        match prop
        {
            ServiceProperty::PortRange =>
                {
                    Ok(self.get_properties().get(&prop).unwrap())
                }
            _ => Err(ServiceError::PropertyNotFound(prop))
        }
    }

    async fn set_property(&mut self, prop: ServiceProperty,_:Value) -> Result<(), ServiceError>
    {
        match prop
        {
            ServiceProperty::PortRange => Err(ServiceError::ReadOnlyProperty(prop)),
            _ => Err(ServiceError::PropertyNotFound(prop))
        }
    }

    fn permission_hooks(&self) -> Option<Box<&dyn ServicePermissionHooks>>
    {
        Some(Box::new(self))
    }
    fn auth(&self) -> Option<Box<&dyn ServiceAuth>>
    {
        None
    }
}

impl FTPService
{
    pub fn new(units:Vec<String>) -> Self
    {
        let mut properties : HashMap<ServiceProperty,Value> = HashMap::new();
        properties .insert(
            ServiceProperty::PortRange,Value::Array(
                vec![
                    Value::Number(Number::from(30000)),
                    Value::Number(Number::from(31000))
                ]
            )
        );


        FTPService
        {
            ftp_service: Box::new(
                SystemdService::new(
                    "ftp",
                    units,
                    PathBuf::from(
                        match detect_distro_family()
                        {
                            DistroFamily::Rh => "/etc/vsftpd/vsftpd.conf",
                            _ => "/etc/vsftpd.conf"
                        }
                    ),
                    vec![UserPermissions::ServicesFtpAccess],
                    properties
                )
            ),
            userlist_file: PathBuf::from("/etc/vsftpd.userlist"),
        }
    }

    async fn touch_userlist_file(&self) -> Result<(), Error>
    {
        let fname = self.get_configuration_file().to_str().unwrap();

        let stat = Stat(&fname,None,CmdConfig::default())
            .run()
            .await;

        if let Ok(Some(output)) = stat && output.exit_code!=0
        {
            let transaction = Transaction::new(
                vec![
                    Touch(&fname, CmdConfig::default()),
                    Chmod(&FileSystemPermissions::from_mode(0o600), None, &fname, false, CmdConfig::default())
                ]
            );

            let _ = transaction.execute().await?;
        }


        Ok(())
    }

    pub async fn get_passive_ports(&mut self) -> Result<(u32, u32),ServiceError>
    {
        let pasv_ports = self
            .get_property(ServiceProperty::PortRange).await?
            .as_array()
            .unwrap()
            .iter()
            .map(|p| p.as_u64().unwrap() as u32)
            .collect::<Vec<u32>>();

        Ok((pasv_ports[0],pasv_ports[1]))
    }

    async fn patch_configuration(&mut self) -> Result<(),ServiceError>
    {
        let mut cfg_default_params = (*VSFTPD_CONF).clone();

        let userlist_path = self.userlist_file.clone();
        let userlist_fname = userlist_path.to_str().unwrap();

        cfg_default_params.insert("userlist_file", &userlist_fname);

        let pasv_ports = self.get_passive_ports().await?;

        let port_min = pasv_ports.0.to_string();
        let port_max = pasv_ports.1.to_string();

        cfg_default_params.insert("pasv_min_port", &port_min);
        cfg_default_params.insert("pasv_max_port", &port_max);

        let cmd = Cat(self.get_configuration_file().to_str(),CmdConfig::default())
            .run()
            .await
            .map_err(|e| ServiceError::Configuration(e.to_string()))?
            .ok_or_else(|| ServiceError::Configuration("Unable to read configuration".to_string()))?
            .is_success()
            .map_err(|e| ServiceError::Configuration(e.to_string()))?;

        let mut cfg = cmd.stdout.lines().map(|x| x.to_string()).collect::<Vec<String>>();
        let mut new_cfg = cfg.clone();

        let mut updated = false;

        for (idx, line) in cfg.iter_mut().enumerate()
        {
            let tokens = line
                .trim_matches(['#','\r','\n'])
                .split('=')
                .map(|x| x.trim())
                .collect::<Vec<&str>>();

            if tokens.len() >= 2
            {
                let key = tokens[0];

                if let Some(value) = cfg_default_params.remove(key)
                {
                    if line.trim().starts_with('#') || tokens[1] != value
                    {
                        new_cfg[idx] = format!("{}={}", key, value);
                    }
                }
            }
        }

        //adds the leftovers at the end of the new_cfg
        if cfg_default_params.len() > 0
        {
            updated = true;

            for (key,value) in cfg_default_params.iter()
            {
                new_cfg.push(format!("{}={}", key, value));
            }
        }

        if updated
        {
            let tmp_filename = match self.cfg.file_name()
            {
                Some(f) => format!("{}.tmp",f.to_str().unwrap()),
                None => "vsftpd.tmp".to_string()
            };

            let mut tmp_fullpath = temp_dir();
            tmp_fullpath.push(tmp_filename);

            let mut handle = File::create(&tmp_fullpath)
                .map_err(|e| ServiceError::TmpFileCreate(tmp_fullpath.clone(),e.to_string()))?;

            handle.write_all(cfg.join("\n").as_bytes())
                .map_err(|e| ServiceError::TmpFileWrite(tmp_fullpath.clone(),e.to_string()))?;

            MV(tmp_fullpath.to_str().unwrap(),self.cfg.to_str().unwrap(),CmdConfig::default())
                .run()
                .await
                .map_err(|e| ServiceError::TmpFileMove(tmp_fullpath,self.cfg.clone(),e.to_string()))?;

        }

        Ok(())
    }

    async fn setup_firewall(&self, add:bool,port_min:u32, port_max:u32) -> Result<(),ServiceError>
    {
        let mut cmd:Vec<CommandLine> = Vec::new();

        let firewall_state = Firewall(FirewallAction::State,false,false,CmdConfig::default()).run().await;

        if let Ok(Some(s)) = firewall_state && (s.exit_code==0) && (s.stdout.trim()=="running")
        {
            cmd.push(Firewall(
                (if add {FirewallAction::AddService} else {FirewallAction::RemoveService})("ftp".to_string()),
                true,
                true,
                CmdConfig::default()
            ));

            cmd.push(Firewall(
                (if add {FirewallAction::AddPort} else {FirewallAction::RemovePort})(FirewallPort::PortRange(port_min,port_max),Protocol::TCP),
                true,
                true,
                CmdConfig::default()
            ));

            cmd.push(SeLinuxSetBool("ftpd_full_access",add,true,true,CmdConfig::default()));
            cmd.push(SeLinuxSetBool("ftpd_use_passive_mode",add,true,true,CmdConfig::default()));
            cmd.push(Firewall(FirewallAction::Reload,false,false,CmdConfig::default()));

            let transaction = Transaction::new(cmd);
            match transaction.execute().await
            {
                Ok(_) => return Ok(()),
                Err(e) => return Err(ServiceError::Firewall(e.to_string()))
            }
        }
        Ok(())
    }

}


#[async_trait]
impl RemoteService for FTPService
{
    async fn start(&mut self) -> Result<(), Error>
    {
        self.patch_configuration().await?;
        
        if detect_distro_family().eq(&DistroFamily::Rh)
        {
            let pasv_ports = self.get_passive_ports().await?;
            self.setup_firewall(true, pasv_ports.0, pasv_ports.1).await?;
        }
        self.ftp_service.start().await
    }

    async fn stop(&mut self) -> Result<(), Error>
    {
        self.ftp_service.stop().await?;
        
        if detect_distro_family().eq(&DistroFamily::Rh)
        {
            let pasv_ports = self.get_passive_ports().await?;
            self.setup_firewall(true, pasv_ports.0, pasv_ports.1).await.map_err(|e| Error::new(e))?;
        }
        
        Ok(())
    }
    
    async fn restart(&mut self) -> Result<(), Error>
    {
        self.ftp_service.restart().await
    }

    async fn is_active(&self) -> Result<bool, Error>
    {
        self.ftp_service.is_active().await
    }

    async fn service_name(&self) -> &'static str
    {
        self.ftp_service.service_name().await
    }
}