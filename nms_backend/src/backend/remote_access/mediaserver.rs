use std::collections::HashMap;
use std::ops::{Deref, DerefMut};
use std::path::PathBuf;
use anyhow::Error;
use async_trait::async_trait;
use serde_json::{Value};
use crate::backend::remote_access::{DockerService, RemoteService, Service, ServiceAuth, ServiceError, ServicePermissionHooks, ServiceProperties, ServiceProperty};
use crate::backend::utils::{detect_distro_family, DistroFamily};
use crate::cmdl::{CmdConfig, CommandLine, Transaction, Executable};
use crate::cmdl::firewall::{Firewall, FirewallAction, FirewallPort};
use crate::cmdl::selinux::Protocol;

static JELLYFIN_DISCOVERY_PORT:u32 = 7359;
static JELLYFIN_SERVICE_PORT:u32 = 8096;
pub struct MEDIAService
{
    media_service: Box<DockerService>,
}

impl Deref for MEDIAService
{
    type Target = DockerService;
    fn deref(&self) -> &Self::Target
    {
        &self.media_service
    }
}

impl DerefMut for MEDIAService
{
    fn deref_mut(&mut self) -> &mut Self::Target
    {
        &mut self.media_service
    }
}

#[async_trait]
impl ServiceProperties for DockerService
{
    fn properties(&self) -> Vec<ServiceProperty>
    {
        vec![ServiceProperty::Port, ServiceProperty::Path]
    }

    async fn get_property(&mut self, prop: ServiceProperty) -> Result<&Value, ServiceError>
    {
        match prop
        {
            ServiceProperty::Port|ServiceProperty::Path => Ok(self.service.properties.get(&prop).unwrap_or_else(|| &Value::Null)),
            _ => Err(ServiceError::PropertyNotFound(prop))
        }
    }

    async fn set_property(&mut self, prop: ServiceProperty,value:Value) -> Result<(), ServiceError>
    {
        match prop
        {
            ServiceProperty::Path|ServiceProperty::Port =>
                {
                    self.service.properties.insert(prop,value);
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
impl ServiceProperties for MEDIAService
{
    fn properties(&self) -> Vec<ServiceProperty>
    {
        vec![ServiceProperty::Port, ServiceProperty::Path]
    }

    async fn get_property(&mut self, prop: ServiceProperty) -> Result<&Value, ServiceError>
    {
        match prop
        {
            ServiceProperty::Port|ServiceProperty::Path =>
                {
                    Ok(self.service.properties.get(&prop).unwrap())
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
                    self.service.properties.insert(prop,value);
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
impl MEDIAService
{
    pub fn new(image_name:String, container_name:String, port:u32,path:Option<PathBuf>) -> MEDIAService
    {
        let mut volumes = HashMap::from([
            ("/var/jellyfin/cache".to_string(),"/cache".to_string()),
            ("/var/jellyfin/config".to_string(),"/config".to_string())
        ]);

        let mut props:HashMap<ServiceProperty,Value> = HashMap::new();

        if let Some(media_root) = path
        {
            let pth = media_root.to_str().unwrap().to_string();
            volumes.insert(pth.clone(),"/media".to_string());
            props.insert(ServiceProperty::Path,Value::String(pth));
        }
        else
        {
            props.insert(ServiceProperty::Path,Value::Null);
        }

        props.insert(ServiceProperty::Port,Value::from(port));

        MEDIAService {
            media_service: Box::new(
                DockerService {
                    service: Service::new(
                        "mediaserver",
                        vec![],
                        props
                    ),
                    image_name,
                    container_name,
                    volumes,
                    port_forwarding: vec![
                        (port, JELLYFIN_SERVICE_PORT),
                        (JELLYFIN_DISCOVERY_PORT, JELLYFIN_DISCOVERY_PORT)
                    ]
                }
            )
        }
    }

    async fn setup_firewall(&mut self,add:bool) -> Result<(), ServiceError>
    {
        let mut cmd:Vec<CommandLine> = Vec::new();

        let firewall_state = Firewall(FirewallAction::State,false,false,CmdConfig::default()).run().await;

        if let Ok(Some(s)) = firewall_state && (s.exit_code==0) && (s.stdout.trim()=="running")
        {
            let port_value = self.get_property(ServiceProperty::Port).await?;

            if let Some(port) = port_value.as_u64()
            {
                cmd.push(Firewall(
                    (if add { FirewallAction::AddPort } else { FirewallAction::RemovePort })(FirewallPort::Port(port as u32), Protocol::TCP),
                    true,
                    true,
                    CmdConfig::default(),
                ));

                cmd.push(Firewall(
                    (if add { FirewallAction::AddPort } else { FirewallAction::RemovePort })(FirewallPort::Port(JELLYFIN_DISCOVERY_PORT), Protocol::UDP),
                    true,
                    true,
                    CmdConfig::default(),
                ));


                cmd.push(Firewall(FirewallAction::Reload, false, false, CmdConfig::default()));

                let transaction = Transaction::new(cmd);
                match transaction.execute().await
                {
                    Ok(_) => return Ok(()),
                    Err(e) => return Err(ServiceError::Firewall(e.to_string()))
                }
            }
        }

        Ok(()) //if the firewall is not there OR is inactive -- who cares?

    }
}

#[async_trait]
impl RemoteService for MEDIAService
{
    async fn start(&mut self) -> Result<(), Error>
    {
        if detect_distro_family().eq(&DistroFamily::Rh)
        {
            self.setup_firewall(true).await?;
        }
        self.media_service.start().await
    }

    async fn stop(&mut self) -> Result<(), Error>
    {
        if detect_distro_family().eq(&DistroFamily::Rh)
        {
            self.setup_firewall(false).await?;
        }
        self.media_service.stop().await
    }
    async fn is_active(&self) -> Result<bool, Error>
    {
        self.media_service.is_active().await
    }

    fn service_name(&self) -> &'static str
    {
        self.service.name
    }
}