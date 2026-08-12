use async_trait::async_trait;
use crate::backend::permissions::UserPermissions;
use crate::backend::remote_access::{ServiceAuth, ServiceError, ServicePermissionHooks, ServiceProperties, ServiceProperty, SystemdService};
use crate::cmdl::coreutils::{Cat, MV};
use regex::RegexBuilder;
use crate::cmdl::passwd::{ GPasswd, GPasswdAction, UserMod, UserModAction};
use crate::cmdl::selinux::{SelinuxManagePort, SelinuxManagePortAction, Protocol, SelinuxManageContext, SelinuxManageContextAction, RestoreContext, SeLinuxSetBool};
use crate::cmdl::firewall::{FirewallPort,FirewallAction,Firewall};
use crate::cmdl::{CmdConfig, CommandLine, Executable, Transaction};
use serde_json::{Value};
use configparser::ini::Ini;
use std::collections::HashMap;
use std::env::temp_dir;
use std::fs::File;
use std::io::{Write};
use std::ops::{Deref, DerefMut};
use std::path::PathBuf;
use std::str::FromStr;
use anyhow::Error;
use crate::backend::utils::{detect_distro_family, DistroFamily};
use crate::cmdl::smb::{SMBPasswd, SMBPasswdAction};
use super::RemoteService;

// static SAMBASHARE_GRP:&'static str="sambashare";
static SMB_CFG_SECTION:&'static str="NMS";

pub struct SMBService
{
    smb_service: Box<SystemdService>,
    user_group: String
}

impl Deref for SMBService
{
    type Target = SystemdService;
    fn deref(&self) -> &Self::Target
    {
        &self.smb_service
    }
}

impl DerefMut for SMBService
{
    fn deref_mut(&mut self) -> &mut Self::Target
    {
        &mut self.smb_service
    }
}

#[async_trait]
impl ServicePermissionHooks for SMBService
{
    async fn permission_granted(&self, username:&str)
    {
        let _ = UserMod(UserModAction::SetGroups(username,&self.user_group,true),false,CmdConfig::default()).run().await;
    }

    async fn permission_revoked(&self, username: &str)
    {
        let _ = GPasswd(GPasswdAction::RemoveGroup(username,&self.user_group), CmdConfig::default()).run().await;
    }

    async fn user_deleted(&self, username: &str)
    {
        self.permission_revoked(username).await;
    }

    async fn get_trigger_permissions(&self) -> &[UserPermissions]
    {
        self.smb_service.service.trigger_perms()
    }


}
#[async_trait]
impl ServiceProperties for SMBService
{
    fn properties(&self) -> Vec<ServiceProperty>
    {
        vec![ServiceProperty::Mountpoint]
    }

    async fn get_property(&mut self, prop: ServiceProperty) -> Result<&Value, ServiceError>
    {
        match prop
        {
            ServiceProperty::Mountpoint =>
                {
                    Ok(self.get_properties().get(&prop).unwrap())
                }
            _ => Err(ServiceError::PropertyNotFound(prop))
        }
    }

    async fn set_property(&mut self, prop: ServiceProperty,value:Value) -> Result<(), ServiceError>
    {
        match prop
        {
            ServiceProperty::Mountpoint =>
                {
                    self.get_properties_mut().insert(prop,value);
                    Ok(())
                }
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

impl SMBService
{
    pub fn new(units:Vec<String>, mountpoint:Option<PathBuf>, group:String) -> Self
    {
        let mut properties : HashMap<ServiceProperty,Value> = HashMap::new();

        properties.insert(ServiceProperty::Mountpoint,match mountpoint {
            Some(m) => Value::String(m.to_str().unwrap().to_string()),
            None => Value::Null
        });

        SMBService
        {
            smb_service: Box::new(
                SystemdService::new(
                    "smb",
                    units,
                    PathBuf::from("/etc/samba/smb.conf"),
                    vec![UserPermissions::ServicesSmbAccess],
                    properties
                )
            ),
            user_group: group
        }
    }

    async fn flush_config(&mut self) -> Result<(), ServiceError>
    {
        let cfg_fname = self
            .get_configuration_file()
            .to_str()
            .ok_or_else(||ServiceError::Configuration("Malformed path to smb configuration".to_string()))?
            .to_string();

        let output = Cat(
            Some(cfg_fname.clone()),
            CmdConfig::default()
        )
            .run()
            .await
            .map_err(|e| ServiceError::Configuration(e.to_string()))?
            .ok_or_else(|| ServiceError::Configuration("Unable to read smb configuration file".to_string()))?;

        let mut cfg = Ini::new();

        let mountpoint =self
            .get_property(ServiceProperty::Mountpoint)
            .await
            .map_err(|e| ServiceError::Configuration(e.to_string()))?
            .as_str()
            .ok_or_else(||ServiceError::Configuration("Unable to read mount point".to_string()))?;

        cfg
            .read(output.stderr)
            .map_err(|e| ServiceError::Configuration(e.to_string()))?;

        cfg.set(SMB_CFG_SECTION,"path",Some(mountpoint.to_string()));
        cfg.set(SMB_CFG_SECTION,"valid users",Some(format!("@{}",self.user_group)));
        cfg.set(SMB_CFG_SECTION,"writable",Some("yes".to_string()));

        let new_cfg = cfg.writes();

        let tmp_filename = match self.cfg.file_name()
        {
            Some(f) => format!("{}.tmp",f.to_str().unwrap()),
            None => "smbcfg.tmp".to_string()
        };

        let mut tmp_fullpath = temp_dir();
        tmp_fullpath.push(tmp_filename);

        let mut handle = File::create(&tmp_fullpath)
            .map_err(|e| ServiceError::TmpFileCreate(tmp_fullpath.clone(),e.to_string()))?;

        handle.write_all(new_cfg.as_bytes())
            .map_err(|e| ServiceError::TmpFileWrite(tmp_fullpath.clone(),e.to_string()))?;

        MV(tmp_fullpath.to_str().unwrap(),cfg_fname,CmdConfig::default())
            .run()
            .await
            .map_err(|e| ServiceError::TmpFileMove(tmp_fullpath,self.cfg.clone(),e.to_string()))?;

        Ok(())


    }

    async fn setup_selinux(&mut self, add:bool) -> Result<(), ServiceError>
    {
        let mut cmd:Vec<CommandLine> = Vec::new();

        if let Ok(value) = self.get_property(ServiceProperty::Mountpoint).await &&
            let Some(mountpoint) = value.as_str()
        {
            let selinux_contexes: HashMap<String, String> = HashMap::from([
                ("home_root_t".to_string(), mountpoint.to_string()),
                ("user_home_dir_t".to_string(), format!("{}/(.*)",mountpoint)),
                ("user_home_t".to_string(), format!("{}/(.*)(/.*)+",mountpoint)),
            ]);

            for (ctx,pth) in selinux_contexes.iter()
            {
                cmd.push(SelinuxManageContext(
                    if add { SelinuxManageContextAction::Add } else {SelinuxManageContextAction::Remove},
                    Some(ctx),
                    Some(pth),
                    true,
                    CmdConfig::default(),
                ));
            }

            cmd.push(RestoreContext(mountpoint,true,CmdConfig::default()));
            cmd.push(SeLinuxSetBool("samba_enable_home_dirs",add,true,true,CmdConfig::default()));

            let transaction = Transaction::new(cmd);
            return match transaction.execute().await
            {
                Ok(_) => Ok(()),
                Err(e) => Err(ServiceError::Selinux(e.to_string()))
            };
        }

        Ok(())

    }

    async fn setup_firewall(&self,add:bool) -> Result<(), ServiceError>
    {
        let mut cmd:Vec<CommandLine> = Vec::new();
        
        let firewall_state = Firewall(FirewallAction::State,false,false,CmdConfig::default()).run().await;

        if let Ok(Some(s)) = firewall_state && (s.exit_code==0) && (s.stdout.trim()=="running")
        {
            let mut ports = self.get_ports_from_selinux().await?;
            for (protocol,port) in ports.drain(0..)
            {
                cmd.push(Firewall(
                    (if add { FirewallAction::AddPort } else {FirewallAction::RemovePort})(port, protocol),
                    true,
                    true,
                    CmdConfig::default()
                ));
            }

            cmd.push(Firewall(FirewallAction::Reload,false,false,CmdConfig::default()));

            let transaction = Transaction::new(cmd);
            match transaction.execute().await
            {
                Ok(_) => return Ok(()),
                Err(e) => return Err(ServiceError::Firewall(e.to_string()))
            }
        }
        
        Ok(()) //if the firewall is not there OR is inactive -- who cares?

    }

    async fn get_ports_from_selinux(&self) -> Result<Vec<(Protocol,FirewallPort)>, ServiceError>
    {
        let selinux = SelinuxManagePort::<&str>(
            SelinuxManagePortAction::List,
            None, None, None, None, false,
            CmdConfig::default())
            .run()
            .await
            .map_err(|e| ServiceError::Selinux(e.to_string()))?
            .ok_or_else(|| ServiceError::Selinux("Unable to run selinux".to_string()))?;

        let regex = RegexBuilder::new(r"^[a-zA-Z0-9_]+[ ]+(tcp|udp)[ ]+(.*)$")
            .case_insensitive(true)
            .build()
            .map_err(|e| ServiceError::Selinux(e.to_string()))?;

        let selinux_types = vec!["smbd_port_t","nmbd_port_t"];
        let mut list_ports: Vec<(Protocol,FirewallPort)> = Vec::new();

        for line in selinux.stdout.lines()
        {
            if selinux_types.iter().any(|port_type| line.contains(port_type))
            {
                if let Some(captures) = regex.captures(line.trim()) && (captures.len()>=2)
                {
                    let proto = &captures[0];
                    let ports = &captures[1];

                    for port in ports.split(",")
                    {
                        if let Ok(protocol) = Protocol::from_str(proto) && let Ok(p) = FirewallPort::from_str(port)
                        {
                            list_ports.push((protocol,p));
                        }
                    }
                }
            }
        }

        Ok(list_ports)

    }


}

#[async_trait]
impl ServiceAuth for SMBService
{
    async fn change_password(&self, username: &str, password: &str) -> Result<(), ServiceError>
    {
        SMBPasswd(SMBPasswdAction::Update(password),username,CmdConfig::default())
            .run()
            .await.map_err(|e| ServiceError::SetPassword(username.to_string(),e.to_string()))?;
        Ok(())
    }
}

#[async_trait]
impl RemoteService for SMBService
{
    async fn start(&mut self) -> Result<(), Error>
    {
        self.flush_config().await?;
        if detect_distro_family().eq(&DistroFamily::Rh)
        {
            self.setup_firewall(true).await?;
            self.setup_selinux(true).await?;
        }
        self.smb_service.start().await
    }

    async fn stop(&mut self) -> Result<(), Error>
    {
        self.smb_service.stop().await?;

        if detect_distro_family().eq(&DistroFamily::Rh)
        {
            self.setup_firewall(false).await?;
            self.setup_selinux(false).await?;
        }

        Ok(())
    }

    async fn restart(&mut self) -> Result<(), Error>
    {
        self.smb_service.restart().await
    }

    async fn is_active(&self) -> Result<bool, Error>
    {
        self.smb_service.is_active().await
    }

    async fn service_name(&self) -> &'static str
    {
        self.smb_service.service_name().await
    }
}