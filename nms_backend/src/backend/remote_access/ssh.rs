use async_trait::async_trait;
use crate::backend::permissions::UserPermissions;
use crate::backend::remote_access::{ServiceAuth, ServiceError, ServicePermissionHooks, ServiceProperties, ServiceProperty, SystemdService};
use crate::cmdl::coreutils::{Cat, MV};
use crate::cmdl::passwd::{ChPasswd, UserMod, UserModAction};
use crate::cmdl::{CmdConfig, Executable};
use serde_json::{Number, Value};
use std::collections::HashMap;
use std::env::temp_dir;
use std::fs::File;
use std::io::{Write};
use std::ops::{Deref, DerefMut};
use std::path::PathBuf;
use anyhow::Error;
use super::RemoteService;

pub struct SSHService
{
    ssh_service: Box<SystemdService>,
}

impl Deref for SSHService
{
    type Target = SystemdService;
    fn deref(&self) -> &Self::Target
    {
        &self.ssh_service
    }
}

impl DerefMut for SSHService
{
    fn deref_mut(&mut self) -> &mut Self::Target
    {
        &mut self.ssh_service
    }
}

#[async_trait]
impl ServicePermissionHooks for SSHService
{
    async fn permission_granted(&self, username:&str)
    {
        let _ = UserMod(UserModAction::ChangeShell(username,"/usr/bin/bash"),false,CmdConfig::default()).run().await;
    }

    async fn permission_revoked(&self, username: &str)
    {
        let _ = UserMod(UserModAction::ChangeShell(username,"/usr/sbin/nologin"),false,CmdConfig::default()).run().await;
    }

}
#[async_trait]
impl ServiceProperties for SSHService
{
    fn properties(&self) -> Vec<ServiceProperty>
    {
        vec![ServiceProperty::Port]
    }

    async fn get_property(&mut self, prop: ServiceProperty) -> Result<&Value, ServiceError>
    {
        match prop
        {
            ServiceProperty::Port =>
                {
                    if self.get_properties().get(&prop).is_some()
                    {
                        Ok(self.get_properties().get(&prop).unwrap()) // have to do this otherwise cannot get mut in else branch
                    }
                    else
                    {
                        Ok(self.read_port_from_cfg().await?)
                    }
                }
            #[allow(unreachable_patterns)]
            _ => Err(ServiceError::PropertyNotFound(prop))
        }
    }

    async fn set_property(&mut self, prop: ServiceProperty,value:Value) -> Result<(), ServiceError>
    {
        match prop
        {
            ServiceProperty::Port =>
                {
                    if value.is_number()
                    {
                        let old_value = self.get_properties().get(&prop);
                        if old_value.is_none() || old_value.unwrap().as_u64() != value.as_u64()
                        {
                            self.set_port_to_cfg(value.as_u64().unwrap() as u32).await?;
                        }

                        Ok(())
                    }
                    else
                    {
                        Err(ServiceError::PropertyValue(prop,"number"))
                    }
                }
            #[allow(unreachable_patterns)]
            _ => Err(ServiceError::PropertyNotFound(prop))
        }
    }

    fn permission_hooks(&self) -> Option<Box<&dyn ServicePermissionHooks>>
    {
        Some(Box::new(self))
    }
    fn auth(&self) -> Option<Box<&dyn ServiceAuth>>
    {
        Some(Box::new(self))
    }
}

impl SSHService
{
    pub fn new(units:Vec<String>) -> Self
    {
        let properties : HashMap<ServiceProperty,Value> = HashMap::new();

        // properties.insert(ServiceProperty::Port, Value::Number(Number::from_u128(
        //     match port
        //     {
        //         Some(p) => p as u128,
        //         None => 22
        //     }
        // ).unwrap()
        // ));

        SSHService
        {
            ssh_service: Box::new(
                SystemdService::new(
                    "ssh",
                    units,
                    PathBuf::from("/etc/ssh/sshd_config"),
                    vec![UserPermissions::ServicesSshAccess],
                    properties
                )
            )
        }
    }

    async fn read_port_from_cfg(&mut self) -> Result<&Value, ServiceError>
    {
        let cmd = Cat(self.get_configuration_file().to_str(),CmdConfig::default())
            .run()
            .await
            .map_err(|e| ServiceError::Configuration(e.to_string()))?
            .ok_or_else(|| ServiceError::Configuration("Unable to read configuration".to_string()))?
            .is_success()
            .map_err(|e| ServiceError::Configuration(e.to_string()))?;

        for line in cmd.stdout.lines()
        {
            let mut l = line.trim();

            if (l.len() == 0) || (line.starts_with('#'))
            {
                continue;
            }

            if let Some(idx) = l.find('"')
            {
                l = &l[..idx].trim();
            }

            let parts = l.split_whitespace().collect::<Vec<&str>>();

            if (parts.len() >= 2) && (parts[0].to_lowercase() == "port")
            {
                let port = parts[1].parse::<u128>().map_err(|e| ServiceError::Configuration(e.to_string()))?;

                self.get_properties_mut().insert(ServiceProperty::Port,Value::Number(Number::from_u128(port).unwrap()));

            }

        }

        if self.get_properties().get(&ServiceProperty::Port).is_none()
        {
            self.get_properties_mut().insert(ServiceProperty::Port,Value::Number(Number::from_u128(22 as u128).unwrap()));
        }

        Ok(self.get_properties().get(&ServiceProperty::Port).unwrap())

    }

    async fn set_port_to_cfg(&mut self, port:u32) -> Result<(), ServiceError>
    {
        let cmd = Cat(self.get_configuration_file().to_str(),CmdConfig::default())
            .run()
            .await
            .map_err(|e| ServiceError::Configuration(e.to_string()))?
            .ok_or_else(|| ServiceError::Configuration("Unable to read configuration".to_string()))?
            .is_success()
            .map_err(|e| ServiceError::Configuration(e.to_string()))?;

        let mut cfg = cmd.stdout.lines().map(|x| x.to_string()).collect::<Vec<String>>();

        let new_port_string = format!("Port {}",port);
        let mut updated = false;

        for (i,line) in cfg.iter_mut().enumerate()
        {
            let l = line.trim();
            if l.to_lowercase().starts_with("port") || l.to_lowercase().starts_with("#port")
            {
                cfg[i] = new_port_string;
                updated = true;
                break;
            }
        }

        if updated
        {
            let tmp_filename = match self.cfg.file_name()
            {
                Some(f) => format!("{}.tmp",f.to_str().unwrap()),
                None => "sshd_config.tmp".to_string()
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

            self.get_properties_mut().insert(ServiceProperty::Port,Value::Number(Number::from_u128(port as u128).unwrap()));

        }

        Ok(())
    }
}

#[async_trait]
impl ServiceAuth for SSHService
{
    async fn change_password(&self, username: &str, password: &str) -> Result<(), ServiceError>
    {
        ChPasswd(username,password,CmdConfig::default()).run().await.map_err(|e| ServiceError::SetPassword(username.to_string(),e.to_string()))?;
        Ok(())
    }
}

#[async_trait]
impl RemoteService for SSHService
{
    async fn start(&self) -> Result<(), Error>
    {
        self.ssh_service.start().await
    }

    async fn stop(&self) -> Result<(), Error>
    {
        self.ssh_service.stop().await
    }

    async fn is_active(&self) -> Result<bool, Error>
    {
        self.ssh_service.is_active().await
    }

    fn service_name(&self) -> &'static str
    {
        self.ssh_service.service_name()
    }
}