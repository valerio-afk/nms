pub mod ssh;
pub mod ftp;
pub mod nfs;
pub mod smb;
pub mod web;
pub mod mediaserver;

use async_trait::async_trait;
use crate::backend::permissions::UserPermissions;
use crate::cmdl::systemd::{Systemctl, SystemctlAction};
use crate::cmdl::{CmdConfig, CommandLine, Executable, Transaction};
use serde::{Serialize, Deserialize};
use serde_json::{Value};
use std::collections::HashMap;
use std::error::Error;
use std::fmt::Display;
use std::path::{PathBuf, Path};
use std::sync::Arc;
use tokio::sync::{OnceCell, RwLock};
use crate::backend::config::{AccessService};
use crate::backend::remote_access::ssh::SSHService;
use crate::backend::remote_access::ftp::FTPService;
use crate::backend::remote_access::mediaserver::MEDIAService;
use crate::backend::remote_access::nfs::NFSService;
use crate::backend::remote_access::smb::SMBService;
use crate::backend::remote_access::web::WEBService;
use crate::backend::User;
use crate::cmdl::docker::{DockerInspect, DockerRemove, DockerRestart, DockerRun, DockerStop};
use crate::cmdl::error_filters::stderr_contains;

pub trait AgnosticRemoteService:RemoteService + ServiceProperties {}

pub type AbstractRemoteService = Arc::<RwLock<dyn AgnosticRemoteService + Send + Sync + 'static>>;

static SYSTEM_SERVICES:OnceCell<Vec<AbstractRemoteService>> = OnceCell::const_new();

#[derive(Debug)]
pub enum ServiceError
{
    PropertyNotFound(ServiceProperty),
    PropertyValue(ServiceProperty,&'static str),
    ReadOnlyProperty(ServiceProperty),
    Configuration(String),
    TmpFileCreate(PathBuf, String),
    TmpFileWrite(PathBuf, String),
    TmpFileMove(PathBuf,PathBuf,String),
    SetPassword(String, String),
    InitialisationError(String),
    Selinux(String),
    Firewall(String),
    Systemd(String),
}

impl Display for ServiceError
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result
    {
        match self
        {
            ServiceError::PropertyNotFound(property) => write!(f, "Service property not found: {}", property),
            ServiceError::ReadOnlyProperty(prop) => write!(f, "Service property {} is read-only", prop),
            ServiceError::Configuration(message) => write!(f, "Unable to access configuration file: {}", message),
            ServiceError::PropertyValue(prop, expected) => write!(f, "Expected `{}` for property: {}", expected, prop),
            ServiceError::TmpFileCreate(fname, err) => write!(f, "Unable to create temporary file {}: {}", fname.display(), err),
            ServiceError::TmpFileWrite(fname, err) => write!(f, "Unable to write in temporary file {}: {}", fname.display(), err),
            ServiceError::TmpFileMove(src, dst, err) => write!(f, "Unable to move temporary file {} in {}: {}", src.display(), dst.display(), err),
            ServiceError::SetPassword(uname, err) => write!(f, "Unable to set password for {}: {}", uname, err),
            ServiceError::InitialisationError(err) => write!(f, "Initialisation Error: {}", err),
            ServiceError::Selinux(err) => write!(f, "Error while setting up SeLinux: {}", err),
            ServiceError::Firewall(err) => write!(f, "Error while setting up the firewall: {}", err),
            ServiceError::Systemd(err) => write!(f, "Error while using systemd: {}", err),
        }
    }
}

impl Error for ServiceError {}

#[derive(Debug,Serialize, Deserialize, strum::Display, Hash, Eq, PartialEq, Clone)]
#[serde(rename_all="lowercase")]
pub enum ServiceProperty
{
    Port,
    PortRange,
    Mountpoint,

    #[serde(rename="ip")]
    IpAddr,
    Path
}
#[async_trait]
pub trait ServicePermissionHooks
{
    async fn permission_granted(&self, username:&str);
    async fn permission_revoked(&self, username:&str);
    async fn user_deleted(&self, username:&str);
}

#[async_trait]
pub trait ServiceAuth
{
    async fn change_password(&self, username:&str, password:&str) -> Result<(), ServiceError>;
}

#[async_trait]
pub trait ServiceProperties
{
    fn properties(&self) -> Vec<ServiceProperty>;
    async fn set_property(&mut self, prop: ServiceProperty, value: Value) -> Result<(), ServiceError>;
    async fn get_property(&mut self, prop: ServiceProperty) -> Result<&Value, ServiceError>;

    fn permission_hooks(&self) -> Option<Box<&dyn ServicePermissionHooks>>;
    fn auth(&self) -> Option<Box<&dyn ServiceAuth>>;

}

#[async_trait]
pub trait RemoteService
{
    async fn start(&mut self) -> Result<(),anyhow::Error>;
    async fn stop(&mut self) -> Result<(),anyhow::Error>;
    async fn restart(&mut self) -> Result<(),anyhow::Error>;
    async fn is_active(&self) -> Result<bool,anyhow::Error>;
    async fn service_name(&self) -> &'static str;
}



pub struct Service
{
    name: &'static str,
    trigger_perms: Vec<UserPermissions>,
    properties: HashMap<ServiceProperty,Value>
}

impl Service
{
    pub fn new(name: &'static str,
               trigger_perms: Vec<UserPermissions>,
               properties: HashMap<ServiceProperty,Value>) -> Self
    {
        Service{
            name,
            trigger_perms,
            properties
        }
    }

    pub fn name(&self) -> &'static str
    {
        self.name
    }

    pub fn trigger_perms(&self) -> &Vec<UserPermissions>
    {
        &self.trigger_perms
    }

    pub fn properties(&self) -> &HashMap<ServiceProperty,Value>
    {
        &self.properties
    }

    pub fn properties_mut(&mut self) -> &mut HashMap<ServiceProperty,Value>
    {
        &mut self.properties
    }
}

pub struct SystemdService
{
    service: Service,
    units: Vec<String>,
    cfg: PathBuf,
}

impl SystemdService
{
    pub fn new(name: &'static str,
               units:Vec<String>,
               cfg:PathBuf,
               trigger_perms: Vec<UserPermissions>,
               properties: HashMap<ServiceProperty,Value>

    ) -> Self
    {
        SystemdService{
            service: Service::new(name,trigger_perms, properties),
            units,
            cfg
        }
    }

    pub fn units(&self) -> &Vec<String>
    {
        &self.units
    }

    pub fn get_configuration_file(&self) -> &Path
    {
        self.cfg.as_path()
    }

    pub fn get_properties_mut(&mut self) -> &mut HashMap<ServiceProperty,Value>
    {
        &mut self.service.properties
    }

    pub fn get_properties(&self) -> &HashMap<ServiceProperty,Value>
    {
        &self.service.properties
    }
}

#[async_trait]
impl RemoteService for SystemdService
{
    async fn start(&mut self) -> Result<(),anyhow::Error>
    {
        let mut systemd_cmds:Vec<CommandLine> = Vec::new();

        for unit in &self.units
        {
            systemd_cmds.extend(
                vec![
                    Systemctl(unit,SystemctlAction::Unmask,true,CmdConfig::Empty),
                    Systemctl(unit,SystemctlAction::Enable,true,CmdConfig::Empty),
                    Systemctl(unit,SystemctlAction::Start,true,CmdConfig::Empty),
                ]
            )
        }

        let transaction = Transaction::new_sudo(systemd_cmds);
        transaction.execute().await?;

        Ok(())
    }

    async fn stop(&mut self) -> Result<(),anyhow::Error>
    {
        let mut systemd_cmds:Vec<CommandLine> = Vec::new();
        for unit in &self.units
        {
            systemd_cmds.extend(
                vec![
                    Systemctl(unit,SystemctlAction::Stop,true,CmdConfig::Empty),
                    Systemctl(unit,SystemctlAction::Disable,true,CmdConfig::Empty),
                    Systemctl(unit,SystemctlAction::Mask,true,CmdConfig::Empty),
                ]
            )
        }

        let transaction = Transaction::new_sudo(systemd_cmds);
        transaction.execute().await?;


        Ok(())
    }

    async fn restart(&mut self) -> Result<(),anyhow::Error>
    {
        let units = self.units().iter().cloned().collect::<Vec<_>>();

        let mut cmd: Vec<CommandLine> = Vec::new();

        for unit in units
        {
            cmd.push(Systemctl(unit, SystemctlAction::Restart,false,CmdConfig::Empty));
        }

        let transaction = Transaction::new_sudo(cmd);
        transaction.execute().await?;

        Ok(())
    }

    async fn is_active(&self) -> Result<bool,anyhow::Error>
    {
        let systemd_cmds:Vec<CommandLine> = self.units.iter().map(
            |u| Systemctl(u,SystemctlAction::IsActive,false,CmdConfig::Provided {
                sudo: true,
                strict: false, //systemctl can return 3 if the unit is not running,
                stdin:None,
                cwd: None
            })
        ).collect();

        let transaction = Transaction::new(systemd_cmds);

        let outputs = transaction.execute().await?;

        Ok(outputs.iter().map(|o| o.stdout.trim() == "active").all(|r| r == true))
    }

    async fn service_name(&self) -> &'static str
    {
        self.service.name()
    }
}


pub struct DockerService
{
    service: Service,
    image_name: String,
    container_name: String,
    volumes: HashMap<String, String>,
    port_forwarding: Vec<(u32,u32)>
}

impl DockerService
{
    pub fn new(name: &'static str,
               image_name: String,
               container_name: String,
               trigger_perms: Vec<UserPermissions>,
               properties: HashMap<ServiceProperty,Value>,
               volumes: HashMap<String, String>,
               port_forwarding: Vec<(u32,u32)>

    ) -> Self
    {
        DockerService{
            service: Service::new(name,trigger_perms, properties),
            image_name,
            container_name,
            volumes,
            port_forwarding
        }
    }

    pub fn image_name(&self) -> &str
    {
        &self.image_name
    }

    pub fn container_name(&self) -> &str
    {
        &self.container_name
    }
}

#[async_trait]
impl RemoteService for DockerService
{
    async fn start(&mut self) -> Result<(),anyhow::Error>
    {
        DockerRun(
            self.image_name(),
            self.container_name(),
            Some(self.volumes.iter().map(|(k,v)| (k.as_str(), v.as_str())).collect::<HashMap<_,_>>()),
            None,
            Some(self.port_forwarding.iter().map(|(p1,p2)| (*p1,*p2,None)).collect::<Vec<_>>().as_slice()),
            None,
            true,
            true,
            Some(DockerRestart::UnlessStopped),
            CmdConfig::default()
        ).run().await?;

        Ok(())
    }


    async fn stop(&mut self) -> Result<(),anyhow::Error>
    {
        Transaction::new_sudo(vec![
            DockerStop(self.container_name(),CmdConfig::Empty),
            DockerRemove(self.container_name(),CmdConfig::Empty),
        ])
            .accept_error_if(stderr_contains("No such container"))
            .execute()
            .await?;

        Ok(())
    }

    async fn restart(&mut self) -> Result<(),anyhow::Error>
    {
        self.stop().await?;
        self.start().await?;

        Ok(())
    }

    async fn is_active(&self) -> Result<bool,anyhow::Error>
    {
        let docker = DockerInspect(
            self.container_name(),
            &["-f","{{.State.Running}}"],
            CmdConfig::default())
            .run()
            .await?
            .ok_or_else(|| anyhow::Error::msg(format!("Unable to get state of docker container {}",self.container_name())))?;

        if docker.exit_code != 0 && docker.stderr.contains("No such object")
        {
            Ok(false)
        }
        else
        {
            Ok(docker.stdout.trim() == "true")
        }
    }



    async fn service_name(&self) -> &'static str
    {
        self.service.name()
    }
}

impl<T> AgnosticRemoteService for T
where
    T: RemoteService + ServiceProperties,
{}

async fn _remote_services(
    cfg:Option<&HashMap<String,AccessService>>,
    mountpoint: Option<PathBuf>,
    users: Option<&[User]>,
    smb_group:Option<String>
) -> Result<&'static Vec<AbstractRemoteService>,ServiceError>
{
    SYSTEM_SERVICES.get_or_try_init(
        || async
            {
                let mut services:Vec<AbstractRemoteService> = Vec::new();

                let c = cfg.ok_or_else(|| ServiceError::InitialisationError("You have to provide a JSON structure to initialise the system services".to_string()))?;

                //ssh configuration
                if let Some(ssh) = c.get("ssh") && let AccessService::Systemd(sshd) = ssh
                {
                    services.push(Arc::new(RwLock::new(SSHService::new(sshd.get_units()))));
                }
                else
                {
                    Err(ServiceError::InitialisationError("You have to provide a valid configuration for SSH".to_string()))?
                }

                tracing::info!("SSH service initialised");

                //ftp configuration
                if let Some(ftp) = c.get("ftp") && let AccessService::Systemd(ftpd) = ftp
                {
                    services.push(Arc::new(RwLock::new(FTPService::new(ftpd.get_units()))));
                }
                else
                {
                    Err(ServiceError::InitialisationError("You have to provide a valid configuration for VSFTPD".to_string()))?
                }

                tracing::info!("FTP service initialised");

                //nfs configuration
                if let Some(nfs) = c.get("nfs") && let AccessService::Systemd(nfsd) = nfs
                {
                    services.push(Arc::new(RwLock::new(NFSService::new(nfsd.get_units(), mountpoint.clone()).await?)));
                }
                else
                {
                    Err(ServiceError::InitialisationError("You have to provide a valid configuration for NFS".to_string()))?
                }

                tracing::info!("NFS service initialised");

                //smb configuration
                if let Some(smb) = c.get("smb") 
                    && let AccessService::Systemd(smbd) = smb
                    && let Some(grp) = smb_group
                {
                    services.push(Arc::new(RwLock::new(SMBService::new(smbd.get_units(), mountpoint, grp))));
                }
                else
                {
                    Err(ServiceError::InitialisationError("You have to provide a valid configuration for SMB".to_string()))?
                }

                tracing::info!("SMB service initialised");

                //web configuration
                if let Some(web) = c.get("web") && let AccessService::Systemd(nginx) = web
                {
                    services.push(Arc::new(RwLock::new(WEBService::new(nginx.get_units()))));
                }
                else
                {
                    Err(ServiceError::InitialisationError("You have to provide a valid configuration for WEB".to_string()))?
                }

                //media server
                if let Some(ms) = c.get("mediaserver") && let AccessService::Docker(msd) = ms
                {
                    let media_username = &msd.user;
                    let mut media_root:Option<PathBuf> = None;

                    if let Some(media_uname) = media_username && let Some(usrs) = users
                    {
                        for u in usrs
                        {
                            if u.username.eq(media_uname)
                            {
                                media_root = u.home_dir.clone()
                            }
                        }
                    }

                    services.push(Arc::new(RwLock::new(MEDIAService::new(
                        msd.image_name.clone(),
                        msd.container_name.clone(),
                        msd.port,
                        media_root
                    ))));
                }
                else
                {
                    Err(ServiceError::InitialisationError("You have to provide a valid configuration for MEDIASERVER".to_string()))?
                }

                tracing::info!("MEDIASERVER service initialised");

                Ok(services)
            }
    ).await
}
pub async fn init_remote_services(
    cfg:&HashMap<String,AccessService>,
    mountpoint: Option<PathBuf>,
    users:Option<&[User]>,
    smb_group:Option<String>
    
) -> Result<&'static Vec<AbstractRemoteService>,ServiceError>

{
    _remote_services(Some(cfg),mountpoint, users,smb_group).await
}


pub async fn get_remote_services() -> Result<&'static Vec<AbstractRemoteService>,ServiceError>
{
    _remote_services(None,None, None,None).await
}


