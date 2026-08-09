use std::collections::HashMap;
use std::env::temp_dir;
use std::fs::File;
use ipnet::Ipv4Net;
use std::io::{Write};
use std::net::Ipv4Addr;
use regex::Regex;
use std::ops::{Deref, DerefMut};
use std::path::PathBuf;
use std::sync::LazyLock;
use anyhow::Error;
use async_trait::async_trait;
use serde_json::Value;
use crate::backend::remote_access::{RemoteService, ServiceAuth, ServiceError, ServicePermissionHooks, ServiceProperties, ServiceProperty, SystemdService};
use crate::backend::utils::{detect_distro_family, DistroFamily};
use crate::cmdl::{CmdConfig, CommandLine, Executable, Transaction};
use crate::cmdl::coreutils::{Cat, MV};
use crate::cmdl::firewall::{Firewall, FirewallAction};
use crate::cmdl::selinux::{RestoreContext, SeLinuxSetBool};

static NFS_DEFAULT_PARAMS:LazyLock<Vec<&'static str>> = LazyLock::new(||{ Vec::from(["rw","sync","fsid=0"]) });
static NMS_CFG_TAG:&'static str = "#nms";

pub struct NFSService
{
    nfs_service: Box<SystemdService>,
}

impl Deref for NFSService
{
    type Target = SystemdService;
    fn deref(&self) -> &Self::Target
    {
        &self.nfs_service
    }
}

impl DerefMut for NFSService
{
    fn deref_mut(&mut self) -> &mut Self::Target
    {
        &mut self.nfs_service
    }
}

#[async_trait]
impl ServiceProperties for NFSService
{
    fn properties(&self) -> Vec<ServiceProperty>
    {
        vec![ServiceProperty::Mountpoint, ServiceProperty::IpAddr]
    }

    async fn get_property(&mut self, prop: ServiceProperty) -> Result<&Value, ServiceError>
    {
        match prop
        {
            ServiceProperty::Mountpoint|ServiceProperty::IpAddr =>
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
            ServiceProperty::Mountpoint|ServiceProperty::IpAddr =>
            {
                self.get_properties_mut().insert(prop,value);
                Ok(())
            }
            _ => Err(ServiceError::PropertyNotFound(prop))
        }
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

#[async_trait]
impl RemoteService for NFSService
{
    async fn start(&mut self) -> Result<(), Error>
    {
        self.flush_config().await?;

        if detect_distro_family().eq(&DistroFamily::Rh)
        {
            self.setup_firewall(true).await?;
        }

        self.nfs_service.start().await
    }

    async fn stop(&mut self) -> Result<(), Error>
    {
        self.flush_config().await?;
        self.nfs_service.stop().await?;

        if detect_distro_family().eq(&DistroFamily::Rh)
        {
            self.setup_firewall(false).await?;
        }

        Ok(())
    }

    async fn restart(&mut self) -> Result<(), Error>
    {
        self.nfs_service.restart().await
    }

    async fn is_active(&self) -> Result<bool, Error>
    {
        self.nfs_service.is_active().await
    }

    async fn service_name(&self) -> &'static str
    {
        self.nfs_service.service_name().await
    }
}

impl NFSService
{
    pub async fn new(units:Vec<String>, mountpoint:Option<PathBuf>) -> Result<NFSService, ServiceError>
    {
        let mut properties : HashMap<ServiceProperty,Value> = HashMap::new();

        properties.insert(ServiceProperty::Mountpoint, match mountpoint {
            Some(m) => Value::String(m.to_str().unwrap().to_string()),
            None => Value::Null
        });

        properties.insert(ServiceProperty::IpAddr,Value::Null);

        let mut nfs = NFSService {
            nfs_service: Box::new(
                SystemdService::new(
                    "nfs",
                    units,
                    PathBuf::from("/etc/exports"),
                    vec![],
                    properties
                )
            )
        };

        nfs.load_configuration(false).await?;

        Ok(nfs)
    }

    async fn load_configuration(&mut self, override_mountpoint: bool) -> Result<(), ServiceError>
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
            if line.contains(NMS_CFG_TAG)
            {
                let re = Regex::new(r"[ \t]*(.*?)[ \t]+(([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,3})?)[ \t]*\((.*?)\)").unwrap();
                if let Some(captures) = re.captures(line)
                {
                    let mountpoint = &captures[1];
                    let addr = &captures[2];

                    let props = self.get_properties_mut();
                    let cfg_mp = props.get_mut(&ServiceProperty::Mountpoint);

                    if (cfg_mp.is_none()) || (cfg_mp.unwrap().is_null()) || override_mountpoint
                    {
                        props.insert(ServiceProperty::Mountpoint,Value::String(mountpoint.to_string()));
                    }


                    if addr.parse::<Ipv4Net>().is_ok() || addr.parse::<Ipv4Addr>().is_ok()
                    {
                        props.insert(ServiceProperty::IpAddr,Value::String(addr.to_string()));
                    }
                    else {
                        println!("dio porco");
                    }
                }
                break;
            }
        }

        Ok(())
    }

    async fn flush_config(&self) -> Result<(), ServiceError>
    {
        let cmd = Cat(self.get_configuration_file().to_str(),CmdConfig::default())
            .run()
            .await
            .map_err(|e| ServiceError::Configuration(e.to_string()))?
            .ok_or_else(|| ServiceError::Configuration("Unable to read configuration".to_string()))?
            .is_success()
            .map_err(|e| ServiceError::Configuration(e.to_string()))?;


        let mountpoint = self.get_properties().get(&ServiceProperty::Mountpoint)
            .ok_or_else(||ServiceError::PropertyNotFound(ServiceProperty::Mountpoint))?
            .as_str()
            .ok_or_else(||ServiceError::PropertyValue(ServiceProperty::Mountpoint,"path"))?;


        let addr = self.get_properties().get(&ServiceProperty::IpAddr)
            .ok_or_else(||ServiceError::PropertyNotFound(ServiceProperty::IpAddr))?
            .as_str()
            .ok_or_else(||ServiceError::PropertyValue(ServiceProperty::IpAddr,"ipv4 address/subnet"))?;


        let mut cfg = cmd.stdout.lines().map(|s|s.to_string()).collect::<Vec<String>>();
        let mut append = true;


        //I use here a closure to avoid unnecessary cloning
        //despite the boolean "append" is set to false when the configuration line is found
        //rust would still consider `cfg[idx] = cfg_line` a move and thus cannot be used in the append case
        //without a cloning. The append branch is almost surely executed once (bc when nms adds it, it will simply replace it)
        //I madee this closure to avoid cloning bc the line replacement is more probable than append and would have cause
        //many stupid clones
        let cfg_line = || format!("{}\t{}({}) #{}",mountpoint,addr,NFS_DEFAULT_PARAMS.join(","),NMS_CFG_TAG);

        for (idx,line) in cfg.iter().enumerate()
        {
            if line.contains(NMS_CFG_TAG)
            {
                cfg[idx] = cfg_line();
                append = false;
                break;
            }
        }

        if append
        {
            cfg.push(cfg_line());
        }

        let tmp_filename = match self.cfg.file_name()
        {
            Some(f) => format!("{}.tmp",f.to_str().unwrap()),
            None => "exports.tmp".to_string()
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

        Ok(())
    }

    async fn setup_firewall(&self, add:bool) -> Result<(),ServiceError>
    {
        let mut cmd:Vec<CommandLine> = Vec::new();

        let firewall_state = Firewall(FirewallAction::State,false,false,CmdConfig::default()).run().await;

        if let Ok(Some(s)) = firewall_state && (s.exit_code==0) && (s.stdout.trim()=="running")
        {
            cmd.push(Firewall(
                (if add {FirewallAction::AddService} else {FirewallAction::RemoveService})("nfs".to_string()),
                true,
                true,
                CmdConfig::default()
            ));

            let mountpoint = self.get_properties().get(&ServiceProperty::Mountpoint)
                .ok_or_else(||ServiceError::PropertyNotFound(ServiceProperty::Mountpoint))?
                .as_str()
                .ok_or_else(||ServiceError::PropertyValue(ServiceProperty::Mountpoint,"path"))?;

            cmd.push(SeLinuxSetBool("nfs_export_all_rw",add,true,true,CmdConfig::default()));
            cmd.push(SeLinuxSetBool("nfs_export_all_ro",false,true,true,CmdConfig::default()));
            cmd.push(SeLinuxSetBool("use_nfs_home_dirs",add,true,true,CmdConfig::default()));
            cmd.push(RestoreContext(mountpoint,true,CmdConfig::default()));
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