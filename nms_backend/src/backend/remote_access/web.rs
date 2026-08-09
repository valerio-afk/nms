use async_trait::async_trait;
use crate::backend::utils::{detect_distro_family, DistroFamily};
use crate::cmdl::coreutils::{Cat, MV};
use crate::cmdl::{CmdConfig,  Executable};
use serde_json::Value;
use std::collections::HashMap;
use std::env::temp_dir;
use std::fs::File;
use std::io::Write;
use std::ops::{Deref};
use std::path::PathBuf;
use std::sync::{Arc};
use std::time::Duration;
use tokio;
use tokio::sync::RwLock;
use tokio::time::sleep;
use anyhow::Error;
use crate::backend::msg::{LogErrors, LogInfos, LogWarnings, LoggerMessages};
use super::{RemoteService, ServiceAuth, ServiceError, ServicePermissionHooks, ServiceProperties, ServiceProperty, SystemdService};

static NGINX_BLOCK:[&'static str;2] = ["/box", "/api"];



pub struct WEBService
{
    web_service: Arc<RwLock<SystemdService>>
}

impl Deref for WEBService
{
    type Target = RwLock<SystemdService>;
    fn deref(&self) -> &Self::Target
    {
        &self.web_service
    }
}



#[async_trait]
impl ServiceProperties for WEBService
{
    fn properties(&self) -> Vec<ServiceProperty>
    {
        vec![]
    }

    async fn get_property(&mut self, prop: ServiceProperty) -> Result<&Value, ServiceError>
    {
        Err(ServiceError::PropertyNotFound(prop))
    }

    async fn set_property(&mut self, prop: ServiceProperty,_:Value) -> Result<(), ServiceError>
    {
        Err(ServiceError::PropertyNotFound(prop))
    }

    fn permission_hooks(&self) -> Option<Box<&dyn ServicePermissionHooks>>
    {
        None
    }
    fn auth(&self) -> Option<Box<&dyn ServiceAuth>>
    {
        None
    }
}

impl WEBService
{
    pub fn new(units:Vec<String>) -> Self
    {
        WEBService
        {
            web_service: Arc::new(RwLock::new(SystemdService::new(
                "web",
                units,
                PathBuf::from(match detect_distro_family() {
                    DistroFamily::Rh => "/etc/nginx/conf.d/nms.conf",
                    _ => "/etc/nginx/sites-available/nms"
                }),
                vec![],
                HashMap::new()
                ))
            )
        }
    }

    async fn read_config(&self) -> Result<Vec<String>, ServiceError>
    {
        let this = self.read().await;
        let cmd = Cat(this.get_configuration_file().to_str(),CmdConfig::default())
            .run()
            .await
            .map_err(|e| ServiceError::Configuration(e.to_string()))?
            .ok_or_else(|| ServiceError::Configuration("Unable to read configuration".to_string()))?
            .is_success()
            .map_err(|e| ServiceError::Configuration(e.to_string()))?;

        Ok(cmd.stdout.lines().map(|s| s.to_string()).collect())
    }

    async fn flush_config(&self, new_cfg:Vec<String>) -> Result<(), ServiceError>
    {
        let this = self.read().await;

        let tmp_filename = match this.cfg.file_name()
        {
            Some(f) => format!("{}.tmp",f.to_str().unwrap()),
            None => "nginx.tmp".to_string()
        };

        let mut tmp_fullpath = temp_dir();
        tmp_fullpath.push(tmp_filename);

        let mut handle = File::create(&tmp_fullpath)
            .map_err(|e| ServiceError::TmpFileCreate(tmp_fullpath.clone(),e.to_string()))?;

        handle.write_all(new_cfg.join("\n").as_bytes())
            .map_err(|e| ServiceError::TmpFileWrite(tmp_fullpath.clone(),e.to_string()))?;

        MV(tmp_fullpath.to_str().unwrap(),this.cfg.to_str().unwrap(),CmdConfig::default())
            .run()
            .await
            .map_err(|e| ServiceError::TmpFileMove(tmp_fullpath,this.cfg.clone(),e.to_string()))?;

        Ok(())
    }


}

#[async_trait]
impl RemoteService for WEBService
{
    async fn start(&mut self) -> Result<(), Error>
    {
        let cfg = self.read_config().await?;
        let mut new_cfg = cfg.clone();
        let mut  start_decommenting = false;

        for (idx,l) in cfg.iter().enumerate()
        {
            if ! start_decommenting
            {
                if l.contains("location") && NGINX_BLOCK.iter().any(|block| l.contains(block))
                {
                    start_decommenting = true;
                }
            }

            if start_decommenting
            {
                if l.trim().starts_with('#')
                {
                    new_cfg[idx] = l.trim_start().trim_start_matches('#').to_string();
                }

                if l.contains('}')
                {
                    start_decommenting = false;
                }
            }
        }

        self.flush_config(new_cfg).await?;

        self.restart().await?;

        Ok(())
    }

    async fn stop(&mut self) -> Result<(), Error>
    {
        let cfg = self.read_config().await?;
        let mut new_cfg = cfg.clone();
        let mut  start_commenting = false;

        for (idx,l) in cfg.iter().enumerate()
        {
            if ! start_commenting
            {
                if l.contains("location") && NGINX_BLOCK.iter().any(|block| l.contains(block))
                {
                    start_commenting = true;
                }
            }

            if start_commenting
            {
                if !l.trim().starts_with('#')
                {
                    new_cfg[idx] = format!("#{}", l);
                }

                if l.contains('}')
                {
                    start_commenting = false;
                }
            }
        }

        self.flush_config(new_cfg).await?;

        self.restart().await?;

        Ok(())
    }

    async fn restart(&mut self) -> Result<(), Error>
    {
        let this = Arc::clone(&self.web_service);

        let _ = tokio::spawn(async move { //no need to await it - in needs to run in parallel
            sleep(Duration::from_secs(2)).await;

            LoggerMessages::Warning(LogWarnings::NginxRestart).log();


            match this.write().await.restart().await
            {
                Ok(_) => LoggerMessages::Info(LogInfos::NginxRestarted).log(),
                Err(e) => LoggerMessages::Error(LogErrors::NginxRestarted(&e.to_string())).log(),
            }
        });

        Ok(())
    }

    async fn is_active(&self) -> Result<bool, Error>
    {
        let mut found:Vec<&str> = Vec::new();
        let cfg = self.read_config().await?;

        for l in cfg.iter()
        {
            if l.contains("location") && NGINX_BLOCK.iter().any(|block| l.contains(block))
            {
                if l.trim().starts_with('#')
                {
                    found.push(l);
                }
            }
        }

        Ok(found.len() == 0)
    }

    async fn service_name(&self) -> &'static str
    {
        self.read().await.service_name().await
    }
}