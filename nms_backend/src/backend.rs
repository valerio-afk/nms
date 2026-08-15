use anyhow::anyhow;
use api::v1::jwt::{TokenPurposes, create_token, token_verification};
use api::v1::msg::{StatusMessage, WrappedResponse};
use axum::Json;
use axum::http::StatusCode;
use base64::prelude::*;
use base64::engine::general_purpose::URL_SAFE;
use chrono::TimeDelta;
use config::{CfgDynDNS};
use config::{CfgPool, CfgToken};
use config::{Config, CfgUser};
use crate::cmdl::coreutils::{Cat, Chown, FileSystemPermissions, Mkdir, OSUser, MV};
use crate::cmdl::error_filters::stderr_contains;
use crate::cmdl::net::{NMCLIConnection, NMCLIDevice, WireGuard, WireGuardAction};
use crate::cmdl::others::RSync;
use crate::cmdl::passwd::{GPasswd, GPasswdAction, GetEntPasswd, GroupMod, GroupModAction, Groups};
use crate::cmdl::passwd::{UserDel, UserMod, UserModAction};
use crate::cmdl::zfs::{ZFS, ZFSArgs, ZPoolImportArgs, ZFSQuotaArgs, ZFSQuota};
use crate::cmdl::zfs::{ZFSActions, ZFSListArgs, ZFSListType, ZFSLoadKeyArgs, ZPool, ZPoolActions};
use crate::cmdl::{CmdConfig, CommandLine, Executable, Transaction};
use crate::dev::get_system_disks;
use crate::dev::{Device, DiskState};
use crate::events::{ContextBuilder, ContextData, ContextVariables, EventManager, EventParameters, Events, Trigger};
use crate::task::{BackgroundTaskManager, Task, BackgroundTask};
use crate::vfs::{Capacity, VFS};
use fernet::{Fernet};
use futures::stream::{self, StreamExt};
use indexmap::IndexMap;
use jwt::{JWTClaim};
use msg::{ErrorMessages, LogErrors, LogInfos, LogWarnings, LoggerMessages};
use msg::{SuccessMessages};
use net::{get_network_ifaces, read_wireguard_config_file, write_wireguard_config_file};
use permissions::is_admin;
use permissions::{collapse_permissions};
use regex::RegexBuilder;
use remote_access::AbstractRemoteService;
use remote_access::{get_remote_services, init_remote_services};
use serde::ser::SerializeStruct;
use serde::{Deserialize, Serialize, Serializer};
use serde_json::{Number, Value};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::env::temp_dir;
use std::error::Error;
use std::fmt::{Debug, Display};
use std::marker::Send;
use std::net::{Ipv4Addr, SocketAddrV4};
use std::path::Path;
use std::path::PathBuf;
use std::str::FromStr;
use std::sync::Arc;
use std::time::Duration;
use ipnet::Ipv4Net;
use struct_iterable::Iterable;
use strum::Display;
use sysinfo::Networks;
use tokio::fs::{File, read_to_string, rename};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::sync::{Mutex, OnceCell, RwLock};
use tokio::time::sleep;
use tracing::{error, info};
use utils::{get_quota_for_all, str_to_i64, sudo_group, ts_to_str, get_notifications_count};
use utils::{parse_mbox, InboxMail, flush_mailbox, init_mbox_basepath};
use utils::{try_create_unix_user, get_user_uid, get_user_gid, restore_user_home_dir};
use uuid::Uuid;
use crate::backend::ddns::{ClouDNS, DDNSService, DNSExit, DuckDNS, DynuDDNS, Dynv6, FreeDNS, NoIP};
use crate::backend::net::{VPN_PRIVATE_KEY, VPN_PUBLIC_KEY};
use crate::cmdl::firewall::{Firewall, FirewallAction, FirewallPort};
use crate::cmdl::selinux::Protocol;
use crate::cmdl::systemd::{Systemctl, SystemctlAction};

pub static BACKEND_VERSION:&'static str = env!("CARGO_PKG_VERSION");
static POOL_KEY_PATH: &'static str = "/root/tank.key";

pub type HTTPMessage = (StatusCode, Json<WrappedResponse>);
pub type FastAPIComp<T> = Result<Json<T>, HTTPMessage>; //this type is to make it more compatible with the current frontend

pub mod api;
pub mod config;
pub mod jwt;
pub mod msg;
pub mod permissions;
pub mod utils;
pub mod net;
mod remote_access;
pub mod ddns;

static BACKEND:OnceCell<Arc<Backend>> = OnceCell::const_new();
static NMS_CONFIG_FILE:&str = "nms.conf.json";


pub fn propagate_error<E:Display+Debug+Send>(msg:ErrorMessages, err:E) -> HTTPMessage
{
    let err = msg.wrap_with_status_code(Some(vec![Value::String(err.to_string())]));
    LoggerMessages::Error(LogErrors::HTTPError(&err)).log();

    err
}

pub fn propagate_unknown_error<E:Display+Debug+Send>(err:E) -> HTTPMessage
{
    propagate_error(ErrorMessages::E_UNKNOWN, err)
}

#[derive(Clone,Debug,Serialize)]
pub struct Quota
{
    pub quota:Option<u64>,
    pub used: Option<u64>
}

#[derive(Clone)]
pub struct TemporarySecret
{
    uuid: String,
    username:Option<String>,
    secret:String
}

#[derive(Clone, Debug,Serialize)]
pub struct User
{
    pub username:String,
    pub visible_name:Option<String>,
    pub permissions: Option<Vec<String>>,
    pub quota:Option<Quota>,
    pub sudo: bool,
    pub admin:bool,
    pub first_login_token:Option<String>,
    pub home_dir: Option<PathBuf>,
    pub uid:Option<u32>,
    pub gid:Option<u32>,
    pub notifications:u32,
}

impl User
{
    pub async fn get_notifications(&self) -> Vec<InboxMail>
    {
        parse_mbox(&self.username).await
    }

    pub async fn get_notification_by_id(&self, id:&str, mark_as_read:bool) -> Option<InboxMail>
    {
        let mut mailbox = self.get_notifications().await;
        let mut mail_found:Option<InboxMail> = None;

        if let Some(found) = mailbox.iter_mut().find(|m| m.get_id() == id)
        {
            if mark_as_read
            {
                found.as_read();
                mail_found = Some(found.clone());
            }
        }
        else { return None; }

        if mail_found.is_some() && mark_as_read
        {
            if let Err(e) = flush_mailbox(&self.username, mailbox.iter().collect::<Vec<&InboxMail>>().as_slice()).await
            {
                LoggerMessages::Error(LogErrors::MailFlushError(&e.to_string())).log();
            }
        }

        mail_found
    }
    
    pub async fn delete_notification_by_id(&self, id:&str)
    {
        let mailbox = self.get_notifications()
            .await
            .into_iter()
            .filter(|m| m.get_id() != id)
            .collect::<Vec<InboxMail>>();
        

        if let Err(e) = flush_mailbox(&self.username, mailbox.iter().collect::<Vec<&InboxMail>>().as_slice()).await
        {
            LoggerMessages::Error(LogErrors::MailFlushError(&e.to_string())).log();
        }
    }
}

#[derive(Debug, Serialize)]
pub struct PoolExtensionStatus
{
    pub is_running:bool,
    pub eta:Option<i64>,
    pub progress:Option<f32>
}

#[derive(Debug, Serialize, Clone)]
pub struct NetIOCounter
{
    total_bytes_recv: u64,
    total_bytes_sent: u64,
    bytes_recv: u64,
    bytes_sent: u64,
}

impl Default for NetIOCounter
{
    fn default() -> Self
    {
        NetIOCounter{
            total_bytes_recv: 0,
            total_bytes_sent: 0,
            bytes_recv: 0,
            bytes_sent: 0
        }
    }
}

#[derive(Debug)]
pub struct BackgroundTaskInformation
{
    task_id:String,
    running:bool,
    progress:Option<f32>,
    eta:Option<u32>,
    detail: Result<Option<SuccessMessages>, ErrorMessages>,
}

impl Serialize for BackgroundTaskInformation
{
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        // 3 is the number of fields in the struct.
        let mut state = serializer.serialize_struct("BackgroundTaskInformation", 5)?;

        state.serialize_field("task_id", &self.task_id)?;
        state.serialize_field("running", &self.running)?;
        state.serialize_field("progress", &self.progress)?;
        state.serialize_field("eta", &self.eta)?;

        match &self.detail
        {
            Ok(o) =>
                {
                    if let Some(result) = o
                    {
                        let success = serde_json::to_value(result.wrap(None)).unwrap();
                        state.serialize_field("detail", &success["detail"])?;
                    }
                    else
                    {
                        state.serialize_field("detail", &Option::<String>::None)?;
                    }
                }
            Err(e) =>
                {
                    let err = serde_json::to_value(e.wrap(None)).unwrap();
                    state.serialize_field("detail", &err["detail"])?;
                }
        }

        state.end()
    }
}


impl PoolExtensionStatus
{
    pub fn new(is_running:bool, eta:Option<i64>,progress:Option<f32>) -> Self
    {
        PoolExtensionStatus { is_running, eta, progress }
    }
}

#[derive(Debug, Serialize)]
pub struct PoolProperties
{
    redundancy:bool,
    encryption:bool,
    compression:bool,
    attached_disks:Vec<Device>
}

#[derive(Debug)]
pub struct Pool
{
    pub name:String,
    pub disks:Vec<Device>,
    pub message:Option<String>,
    pub state:Option<String>,
}

impl Serialize for Pool
{
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        // 3 is the number of fields in the struct.
        let mut state = serializer.serialize_struct("BackgroundTaskInformation", 4)?;

        state.serialize_field("name", &self.name)?;
        state.serialize_field("disks", &self.disks.iter().map(|d| d.paths[0].to_string()).collect::<Vec<_>>())?;
        state.serialize_field("message", &self.message)?;
        state.serialize_field("state", &self.state)?;

        state.end()
    }
}


#[derive(Clone, Debug, Serialize)]
pub struct LastScrubReport
{
    pub started:String,
    pub ended: String,
    pub errors: String
}

impl LastScrubReport
{
    pub fn new(started:Option<i64>, ended:Option<i64>, errors:Option<&str>) -> LastScrubReport
    {
        LastScrubReport 
        { 
            started: ts_to_str(started),
            ended: ts_to_str(ended), 
            errors: errors.or(Some("-")).unwrap().to_string()
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct ScrubLiveInfo
{
    pub ongoing:bool,
    pub last: Option<i64>,
}

impl ScrubLiveInfo
{
    pub fn new(ongoing:bool, last:Option<i64>) -> ScrubLiveInfo
    {
        ScrubLiveInfo 
        { 
            ongoing,
            last
        }
    }
}

#[derive(Debug, Serialize, Clone)]
pub struct Snapshot
{
    name:String,
    ref_size:u64
}

impl Snapshot
{
    pub fn new(name:String, ref_size:u64) -> Snapshot
    {
        Snapshot{
            name,
            ref_size
        }
    }
}


pub struct ScrubDetails
{
    last_scrub_report:Option<LastScrubReport>,
    scrub_live_info: Option<ScrubLiveInfo>
}

impl Default for ScrubDetails
{
    fn default() -> Self
    {
        ScrubDetails{
            last_scrub_report: None,
            scrub_live_info: None
        }
    }
}

#[derive(Debug, Deserialize)]
pub enum HomeDirAction
{

    #[serde(rename="k")]
    Keep,
    #[serde(rename="d")]
    Delete,
    #[serde(rename="m")]
    Move
}

#[derive(Debug, Serialize)]
pub struct VPNPeer
{
    name: String,
    ip: Ipv4Addr,
}

impl VPNPeer
{
    pub fn new(name:String, ip:Ipv4Addr) -> Self
    {
        VPNPeer{name, ip}
    }
}


#[derive(Debug, Serialize)]
pub struct DDNSProvider
{
    pub enabled: bool,
    pub username: Option<String>,
    pub last_update: Option<u64>,
    pub next_update: Option<u64>
}

impl DDNSProvider
{
    pub fn new(enabled:bool,
               username:Option<String>,
               last_update:Option<u64>,
               next_update:Option<u64>) -> Self
    {
        DDNSProvider{enabled, username, last_update, next_update}
    }
}

impl Default for DDNSProvider
{
    fn default() -> Self
    {
        DDNSProvider::new(false, None, None, None)
    }
}

#[derive(Debug, Serialize, Deserialize, Display)]
#[serde(rename_all = "lowercase")]
pub enum IfaceStatusAction
{
    #[strum(to_string="connect")]
    Up,
    #[strum(to_string="disconnect")]
    Down
}



pub struct Backend
{
    config:Mutex<Config>,
    users:Mutex<Vec<Arc<RwLock<User>>>>,
    tmp_secrets:Mutex<HashMap<String,TemporarySecret>>,
    event_manager:EventManager,
    background_task_manager: Arc<BackgroundTaskManager<SuccessMessages>>,
    secret_key:String,
    mount: RwLock<Option<VFS>>,
    pool_properties: RwLock<Option<PoolProperties>>,
    net_counter: RwLock<NetIOCounter>,
    snapshots:RwLock<Vec<Snapshot>>,
    scrub_details:RwLock<ScrubDetails>,
    ddns_services:RwLock<HashMap<String,Arc<dyn DDNSService>>>,
}

impl Backend
{
    pub async fn new() -> Arc<Self>
    {
        let backend = Backend{
                config:Mutex::new(Config::default()),
                users:Mutex::new(vec![]),
                tmp_secrets: Mutex::new(HashMap::new()),
                event_manager: EventManager::new(),
                background_task_manager: BackgroundTaskManager::new(),
                secret_key: "prova".to_string(),
                mount: RwLock::new(None),
                pool_properties:RwLock::new(None),
                net_counter: RwLock::new(NetIOCounter::default()),
                snapshots: RwLock::new(Vec::new()),
                scrub_details: RwLock::new(ScrubDetails::default()),
                ddns_services: RwLock::new(HashMap::new()),
        };

        backend.init().await
    }

    pub async fn read_config(&self) -> Result<(),Box<dyn Error + '_>>
    {
        let json = read_to_string(NMS_CONFIG_FILE).await?;

        let mut cfg = self.config.lock().await;

        *cfg = serde_json::from_str(&json)?;

        cfg.cleanup_tokens();

        Ok(())
    }

    async fn _flush_config(&self) -> Result<(),std::io::Error>
    {
        let mut tmp_file = NMS_CONFIG_FILE.to_string();
        tmp_file.push('~');

        let result = File::create(&tmp_file).await;

        match result
        {
            Ok(mut file) =>
                {
                    let cfg = self.config.lock().await;
                    let cfg_serialised = serde_json::to_vec_pretty(&*cfg);

                    match cfg_serialised
                    {
                        Ok(serialised) =>
                            {
                                let result = file.write_all(serialised.as_slice()).await;

                                if let Err(e) = result
                                {
                                    LoggerMessages::Error(LogErrors::CfgWrite(&e.to_string())).log();
                                    return Err(e.into());
                                }

                                let rename_res = rename(tmp_file, NMS_CONFIG_FILE).await;

                                if let Err(e) = rename_res
                                {
                                    LoggerMessages::Error(LogErrors::CfgMove(&e.to_string())).log();
                                    return Err(e.into());
                                }

                                Ok(())
                            }
                        Err(e) =>
                            {
                                LoggerMessages::Error(LogErrors::CfgWrite(&e.to_string())).log();
                                return Err(e.into());
                            }
                    }

                }
            Err(e) =>
                {
                    LoggerMessages::Error(LogErrors::CfgRead(&e.to_string())).log();
                    Err(e.into())
                }
        }
    }

    pub async fn flush_config(&self) -> Result<(), HTTPMessage>
    {
        self._flush_config().await.map_err(|e| propagate_unknown_error(e))
    }

    pub async fn get_task_by_id(&self, id:&str) -> Option<BackgroundTaskInformation>
    {
        if let Some(task) = self.background_task_manager.get_task_by_id(id).await
        {
            let running = task.is_running().await;

            return Some(BackgroundTaskInformation{
                task_id: id.to_string(),
                running,
                progress: task.get_progress(),
                eta: task.get_eta(),
                detail: {
                    if running { Ok(None) }
                    else {
                        let j = task.join().await;
                        match j
                        {
                            Ok(r) => Ok(r),
                            Err(e) =>  {
                                LoggerMessages::Error(LogErrors::TaskError(task.get_name(),&e.to_string())).log();
                                Err(ErrorMessages::E_UNKNOWN)
                            }
                        }
                    }
                }

            });
        }

        None
    }
}

//initialiser Methods

impl Backend
{
    async fn init_configuration(&mut self)
    {
        let read_cfg_result = self.read_config().await;

        if let Err(e) = read_cfg_result
        {
            LoggerMessages::Error(LogErrors::CfgRead(&e.to_string())).log();
            LoggerMessages::Warning(LogWarnings::CfgDefault).log();
            let flush_cfg_result = self._flush_config().await;
            match flush_cfg_result
            {
                Ok(()) => LoggerMessages::Info(LogInfos::NewCfg).log(),
                Err(e) => {
                    LoggerMessages::Error(LogErrors::CfgWrite(&e.to_string())).log();
                    std::process::exit(1)
                }
            }
        }

        let mbox = self.config.lock().await.daemon.mbox_basepath.clone();
        init_mbox_basepath(Some(mbox));

        LoggerMessages::Info(LogInfos::BackendStarted).log();
    }

    async fn init_users(self: &Arc<Self>)
    {
        let reload_user_ft = self.reload_users();

        let task_backend = Arc::clone(self);

        self.event_manager.register_multiple_events (
            &[&Events::UserCreated,&Events::UserDeleted, &Events::UserModified],
            Arc::new(
                Box::new(
                    move |(trigger,ctx):&(Trigger,Option<ContextData>)|
                        {
                            let b = Arc::clone(&task_backend);
                            let t = trigger.clone();
                            let context = ctx.clone();
                            Box::pin(
                                async move
                                    {
                                        b.reload_users().await;

                                        if let Trigger::Event(e) = t &&
                                            let Some(ctx) = context &&
                                            let Some(account) = ctx.get(&ContextVariables::Account)

                                        {
                                            LoggerMessages::Info(LogInfos::AccessServiceTrigger).log();

                                            if e != Events::UserDeleted
                                            {
                                                match b.get_user(account).await
                                                {
                                                    Ok(u) => {
                                                        let user = u.read().await;
                                                        let perms = user.permissions.as_ref();
                                                        if let Err(e) = Backend::trigger_remote_access_services_permissions(account.as_str(),perms,false).await
                                                        {
                                                            LoggerMessages::Error(LogErrors::AccessServiceTriggerError(&e.to_string())).log();
                                                        }
                                                    }
                                                    Err(e) => { LoggerMessages::Error(LogErrors::AccessServiceTriggerError(&e.1.to_string())).log(); }
                                                }

                                            }
                                            else
                                            {
                                                if let Err(e) = Backend::trigger_remote_access_services_permissions(account.as_str(),None,true).await
                                                {
                                                    LoggerMessages::Error(LogErrors::AccessServiceTriggerError(&e.to_string())).log();
                                                }
                                            }
                                        }
                                    }
                            )
                        }
                )
            )
            ,
            None
        ).await;

        reload_user_ft.await;
    }

    async fn init_ddns_service_task(self: &Arc<Self>)
    {
        let duration = {
            let cfg = self.config.lock().await;
            let d = cfg.daemon.ddns_refresh_time;

            Duration::from_mins(d as u64).as_secs()
        };

        let task_backend = Arc::clone(self);

        self.event_manager.register_action (
            &Events::Timer,
            Arc::new(
                Box::new(
                    move |(_,_):&(Trigger,Option<ContextData>)|
                        {
                            let b = Arc::clone(&task_backend);
                            Box::pin(
                                async move
                                    {
                                        let mut flush=false;
                                        for (name,provider) in b.ddns_services.read().await.iter()
                                        {
                                            match provider.update().await
                                            {
                                                Ok(_) =>
                                                    {
                                                        LoggerMessages::Info(LogInfos::DDNSUpdated(name)).log();
                                                        let mut cfg = b.config.lock().await;
                                                        cfg.ddns_service_updated(name.as_str());
                                                        flush = true;
                                                    },
                                                Err(e) => LoggerMessages::Error(LogErrors::DDnsUpdate(name,&e.to_string())).log(),
                                            }
                                        }

                                        if flush
                                        {
                                            if let Err(e) = b.flush_config().await
                                            {
                                                LoggerMessages::Error(LogErrors::CfgWrite(&e.1.to_string())).log();
                                            }

                                            if let Err(e) = b.reload_ddns_providers().await
                                            {
                                                LoggerMessages::Error(LogErrors::DDns(&e.1.to_string())).log();
                                            }
                                        }
                                    }
                            )
                        }
                )
            ),
            None,
            Some(vec![EventParameters::Timer(duration)])
        ).await;
    }

    async fn init_net_counters(self: &Arc<Self>)
    {
        let task_backend = Arc::clone(self);

        self.event_manager.register_action(
            &Events::Timer,
            Arc::new(
                Box::new(
                    move |(_trigger,_ctx):&(Trigger,Option<ContextData>)|
                        {
                            let mut net = Networks::new_with_refreshed_list();
                            let b = Arc::clone(&task_backend);
                            Box::pin(
                                async move
                                    {
                                        b.update_users().await;
                                        net.refresh(true);

                                        let mut net_bytes_sent = 0;
                                        let mut net_bytes_recv = 0;


                                        for (_, network) in &net
                                        {
                                            net_bytes_sent += network.total_transmitted();
                                            net_bytes_recv += network.total_received();
                                        }

                                        {
                                            let mut net_counters = b.net_counter.write().await;

                                            if (net_counters.total_bytes_recv > 0) && (net_counters.total_bytes_sent > 0)
                                            {
                                                net_counters.bytes_recv = net_bytes_recv - net_counters.total_bytes_recv;
                                                net_counters.bytes_sent = net_bytes_sent - net_counters.total_bytes_sent;
                                            }

                                            net_counters.total_bytes_recv = net_bytes_recv;
                                            net_counters.total_bytes_sent = net_bytes_sent;
                                        }

                                    })
                        }
                )
            ),
            None,
            Some(vec![EventParameters::Timer(3)])
        ).await;
    }

    async fn init_scrub_details_watcher(self: &Arc<Self>)
    {
        let task_backend = Arc::clone(self);

        self.event_manager.register_action(
            &Events::Timer,
            Arc::new(
                Box::new(
                    move |(_trigger,_ctx):&(Trigger,Option<ContextData>)|
                        {
                            let b = Arc::clone(&task_backend);
                            Box::pin(
                                async move
                                    {
                                        b.update_scrub_details().await;
                                    })
                        }
                )
            ),
            None,
            Some(vec![EventParameters::Timer(10)])
        ).await;
    }

    async fn init_remote_service(&self)
    {
        let cfg = self.config.lock().await;

        if let Err(e) = init_remote_services(
            &cfg.access_services,
            self.mountpoint().await,
            Some(self.get_users().await.as_slice()),
            Some(cfg.daemon.user_groups.smb.clone())
        ).await
        {
            error!("{:?}", e);
        }
    }

    async fn init_pool_event_tasks(self: &Arc<Self>)
    {
        let task_backend = Arc::clone(self);

        self.event_manager.register_action(
            &Events::PoolMount,
            Arc::new(
                Box::new(
                    move |(_trigger,_ctx):&(Trigger,Option<ContextData>)|
                        {
                            let b = Arc::clone(&task_backend);
                            Box::pin(
                                async move {
                                    if let Err(e) = b.init_vfs().await
                                    {
                                        LoggerMessages::Error(LogErrors::VFSInit(&e.1.to_string())).log();
                                    }

                                    if let Err(e) = b.init_pool_snapshots().await
                                    {
                                        LoggerMessages::Error(LogErrors::SnapshotInit(&e.1.to_string()));
                                    }

                                    if let  Some(mountpoint) = b.mountpoint().await
                                    {
                                        b.event_manager.start_inotify_task(mountpoint.to_str().unwrap()).await;
                                    }
                                }
                            )
                        }
                )
            ),
            None,
            None
        ).await;

        let task_backend = Arc::clone(self);

        self.event_manager.register_action(
            &Events::PoolUnmount,
            Arc::new(
                Box::new(
                    move |(_trigger,_ctx):&(Trigger,Option<ContextData>)|
                        {
                            let b = Arc::clone(&task_backend);
                            Box::pin(
                                async move {
                                    {
                                        let mut mp = b.mount.write().await;
                                        *mp = None;
                                    }
                                    b.event_manager.stop_inotify_task().await;
                                }
                            )
                        }
                )
            ),
            None,
            None
        ).await;
    }

    pub async fn configure_pool(&self) -> Result<(), HTTPMessage>
    {
        let mut flush = false;

        let mut cfg = self.config.lock().await;
        if cfg.pool.is_none()
        {
            let output = ZFS::<String>(ZFSActions::Get(None),false,CmdConfig::Empty)
                .run()
                .await
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_MOUNT, e))?
                .ok_or_else(|| ErrorMessages::E_POOL_MOUNT.wrap_with_status_code(None))?
                .is_success()
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_MOUNT, e))?;

            let json:Value = serde_json::from_str(&output.stdout).map_err(|e| propagate_error(ErrorMessages::E_POOL_MOUNT, e))?;

            let mut pool_name:Option<String> = None;
            let mut dataset_name:Option<String> = None;
            let mut key_location:Option<String> = None;

            if let Some(data) = json.as_object() &&
               let Some(datasets_object) = data.get("datasets") &&
               let Some(datasets) = datasets_object.as_object()
            {
                //two passes bc order cannot be ensured

                //first pass to find pool_name
                for (name,dataset) in datasets.iter()
                {
                    if let Some(ds) = dataset.as_object() &&
                       let Some(ds_type) = dataset["type"].as_str() &&
                       ds_type == "FILESYSTEM" &&
                       let Some(ds_name) = ds["name"].as_str() &&
                       name == ds_name
                    {

                        pool_name = Some(name.clone());
                        let props = &ds["properties"];

                        if let Some(keyloc) = props["keylocation"].as_object() &&
                           let Some(valueloc) = keyloc["value"].as_str()
                        {
                            key_location = Some(valueloc.replace("file://",""));
                        }

                        break;
                    }
                }

                if let Some(tank) = &pool_name
                {
                    //second pass to find datasetname
                    for (_, dataset) in datasets.iter()
                    {
                        if let Some(ds) = dataset.as_object() &&
                           let Some(ds_name) = ds["name"].as_str() &&
                           let Some(dataset_pool) = ds["pool"].as_str() &&
                           dataset_pool == tank
                            {
                                let tokens = ds_name.split('/').collect::<Vec<&str>>();
                                if tokens.len() == 2 && tokens[0] == tank
                                {
                                    dataset_name = Some(tokens[1].to_string());
                                    break;
                                }
                            }
                    }
                }
            }

            if let Some(pool) = pool_name && let Some(dataset) = dataset_name
            {
                LoggerMessages::Info(LogInfos::PoolUnconfigured(&pool, &dataset)).log();

                if let Some(key) = &key_location
                {
                    LoggerMessages::Info(LogInfos::PoolKeyDetected(key)).log();
                }

                let pool = CfgPool {
                    name: pool,
                    dataset,
                    encryption_key: key_location
                };

                cfg.pool = Some(pool);
                flush = true;

                LoggerMessages::Info(LogInfos::PoolConfigured).log();

            }
        }

        if let Some(pool) = &cfg.pool
        {
            let output = ZFS::<String>(ZFSActions::Get(Some(pool.name.clone())),false,CmdConfig::Empty)
                .run()
                .await
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_MOUNT, e))?
                .ok_or_else(|| ErrorMessages::E_POOL_MOUNT.wrap_with_status_code(None))?
                .is_success()
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_MOUNT, e))?;

            let json:Value = serde_json::from_str(&output.stdout).map_err(|e| propagate_error(ErrorMessages::E_POOL_MOUNT, e))?;
            let dataset_props = &json["datasets"][pool.name.as_str()]["properties"];

            let compression:bool = if let Some(compr) = dataset_props["compression"]["value"].as_str()
            {
                compr.to_lowercase() != "off"
            }
            else { false };

            let encryption:bool = if let Some(compr) = dataset_props["encryption"]["value"].as_str()
            {
                compr.to_lowercase() != "off"
            }
            else { false };
            let mut redundancy = false;

            let output = ZPool(ZPoolActions::Status(pool.name.clone()),false,CmdConfig::Empty)
                .run()
                .await
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_MOUNT, e))?
                .ok_or_else(|| ErrorMessages::E_POOL_MOUNT.wrap_with_status_code(None))?
                .is_success()
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_MOUNT, e))?;

            let json:Value = serde_json::from_str(&output.stdout).map_err(|e| propagate_error(ErrorMessages::E_POOL_MOUNT, e))?;

            let pool_root = &json["pools"][&pool.name]["vdevs"][&pool.name];
            let mut vdevs = &pool_root["vdevs"];

            let mut pool_disks:Vec<Device> = Vec::new();

            if let Some(devs) = vdevs.as_object()
            {
                if devs.len() == 1
                {
                    for (_, v) in devs
                    {
                        if let Some(vdev_type) = v["vdev_type"].as_str() && vdev_type == "raidz"
                        {
                            redundancy = true;
                            vdevs = &v["vdevs"];
                            break;
                        }
                    }
                }

                if let Some(devices) = vdevs.as_object()
                {
                    for (_,d) in devices
                    {
                        if let Some(dtype) = d["vdev_type"].as_str() &&
                            dtype == "disk" &&
                            let Some(subpath) = d["phys_path"].as_str() &&
                            let Some(state) = d["state"].as_str()

                        {
                            if let Ok(dev) = Device::from_subpath(
                                subpath,
                                if let Ok(s) = DiskState::from_str(state) {s} else {DiskState::NEW}
                            ).await
                            {
                                pool_disks.push(dev);
                            }
                        }
                    }
                }
            }

            info!("Detected pool: {}/{}",pool.name,pool.dataset);
            info!("Redundancy: {}",redundancy);
            info!("Encryption: {}",encryption);
            info!("Compression: {}",compression);
            info!("Devices: {}", pool_disks.iter().map(|d|d.paths[0].to_string()).collect::<Vec<_>>().join(","));

            let mut props = self.pool_properties.write().await;
            *props = Some(PoolProperties{
                redundancy,
                encryption,
                compression,
                attached_disks: pool_disks,
            });
        }

        drop(cfg);
        if flush { self.flush_config().await?; }

        Ok(())
    }

    pub async fn init_vfs(&self) -> Result<(), HTTPMessage>
    {
        if let Some((pool,dataset)) = self.get_pool_identifier().await
        {
            let mut vfs = VFS::from_zfs(&pool, &dataset)
                .await
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_MOUNTED,e.unwrap_or("unknown error".to_string())))?;

            vfs.rebuild_tree().await;

            let mut b_vfs = self.mount.write().await;
            *b_vfs = Some(vfs);

            return Ok(());
        }

        Err(ErrorMessages::E_POOL_MOUNTED.wrap_with_status_code(Some(vec![Value::String("Pool not mounted yet".to_string())])))
    }

    pub async fn init_pool_snapshots(&self) -> Result<(), HTTPMessage>
    {
        let output = ZFS::<String>(ZFSActions::List(ZFSListArgs::new(None,Some(ZFSListType::Snapshot),None)),false,CmdConfig::Empty)
            .run()
            .await
            .map_err(|e| propagate_error(ErrorMessages::E_POOL_SNAPSHOTS, e))?
            .ok_or_else(|| ErrorMessages::E_POOL_SNAPSHOTS.wrap_with_status_code(None))?
            .is_success()
            .map_err(|e| propagate_error(ErrorMessages::E_POOL_SNAPSHOTS, e))?;

        let json:Value = serde_json::from_str(&output.stdout).or::<Value>(Ok(Value::Null)).unwrap();
        let mut snapshots:Vec<Snapshot> = Vec::new();

        if let Some(d) = json.as_object() &&
            let Some(datasets) = d.get("datasets") &&
            let Some(list_datasets) = datasets.as_array()
        {
            let mut list_datasets = list_datasets.clone();
            list_datasets.sort_by_key(|k| k.get("createtxg").unwrap_or(&Value::Number(Number::from(0))).as_number().unwrap().as_i128().unwrap() );

            for dataset in list_datasets
            {
                if let Some(dataset) = dataset.as_object()
                {
                    if let Some(tp) = dataset.get("type") &&
                        let Some(dataset_type) = tp.as_str() &&
                        dataset_type == "SNAPSHOT"
                    {
                        let name = &dataset["snapshot_name"];
                        let ref_size = &dataset["properties"]["referenced"]["value"];

                        if let Some(name) = name.as_str() && let Some(size) = ref_size.as_u64()
                        {
                            snapshots.push(Snapshot::new(name.to_string(), size));
                        }
                    }
                }
            }
        }

        let mut snapshot_cache = self.snapshots.write().await;
        *snapshot_cache = snapshots;

        Ok(())
    }

    async fn init_pool(&self)
    {
        if let Err(e) = self.mount(None).await
        {
            LoggerMessages::Error(LogErrors::Automount(&e.1.to_string()));
        }
        if let Err(e) = self.init_vfs().await
        {
            LoggerMessages::Error(LogErrors::VFSInit(&e.1.to_string()));
        }
        if let Err(e) = self.init_pool_snapshots().await
        {
            LoggerMessages::Error(LogErrors::SnapshotInit(&e.1.to_string()));
        }
    }

    async fn init(mut self) -> Arc<Self>
    {
        self.init_configuration().await;
        let be = Arc::new(self);
        be.event_manager.start().await;
        be.init_pool_event_tasks().await;


        if let Err(e) = be.configure_pool().await
        {
            be.deinit_pool().await;
            LoggerMessages::Error(LogErrors::PoolConfig(&e.1.to_string()));
        }
        else
        {
            be.init_pool().await;
        }

        be.init_users().await;

        if let Err(e) = be.reload_ddns_providers().await
        {
            LoggerMessages::Error(LogErrors::DDns(&e.1.to_string()));
        }

        be.init_ddns_service_task().await;
        be.init_net_counters().await;
        be.init_scrub_details_watcher().await;
        be.init_remote_service().await;

        be
    }

    async fn deinit_pool(&self)
    {
        let mut cfg = self.config.lock().await;
        cfg.pool = None;

        let mut pool_props = self.pool_properties.write().await;
        *pool_props = None;

        let mut snapshots = self.snapshots.write().await;
        snapshots.clear();


    }
}

// Network-related Methods

impl Backend
{
    pub async fn reload_ddns_providers(&self) -> Result<(), HTTPMessage>
    {
        let digest = Sha256::digest(self.secret_key.as_bytes());
        let key = URL_SAFE.encode(digest);
        let fernet = Fernet::new(key.as_str())
            .ok_or_else(|| ErrorMessages::E_NET_DDNS_CONFIG.wrap_with_status_code(None))?;


        let mut svc: HashMap<String,Arc<dyn DDNSService>> = HashMap::new();
        let cfg = self.config.lock().await;

        for (name,prov_conf) in cfg.ddns.iter()
        {
            let prov_info = prov_conf.downcast_ref::<Option<CfgDynDNS>>().unwrap();

            if let Some(prov_cfg) = prov_info && prov_cfg.enabled
            {
                match name.to_lowercase().as_str()
                {
                    "noip" => {
                        if let Some(u) = &prov_cfg.username
                        {
                            svc.insert(name.to_string(), Arc::new(NoIP(u.clone(), String::from_utf8(fernet.decrypt(prov_cfg.password.as_str()).unwrap()).unwrap())));
                        }
                    }
                    "duckdns" => {
                        if let Some(domain) = &prov_cfg.username
                        {
                            svc.insert(name.to_string(), Arc::new(DuckDNS(domain.clone(), String::from_utf8(fernet.decrypt(prov_cfg.password.as_str()).unwrap()).unwrap())));
                        }
                    }
                    "dynu" => {
                        if let Some(u) = &prov_cfg.username
                        {
                            svc.insert(name.to_string(), Arc::new(DynuDDNS(u.clone(), String::from_utf8(fernet.decrypt(prov_cfg.password.as_str()).unwrap()).unwrap())));
                        }
                    }
                    "freedns" => { svc.insert(name.to_string(), Arc::new(FreeDNS(String::from_utf8(fernet.decrypt(prov_cfg.password.as_str()).unwrap()).unwrap()))); }
                    "dnsexit" => {
                        if let Some(u) = &prov_cfg.username
                        {
                            svc.insert(name.to_string(), Arc::new(DNSExit(u.clone(), String::from_utf8(fernet.decrypt(prov_cfg.password.as_str()).unwrap()).unwrap())));
                        }
                    }
                    "dynv6" => {
                        if let Some(u) = &prov_cfg.username
                        {
                            svc.insert(name.to_string(), Arc::new(Dynv6(u.clone(), String::from_utf8(fernet.decrypt(prov_cfg.password.as_str()).unwrap()).unwrap())));
                        }
                    }
                    "cloudns" => { svc.insert(name.to_string(), Arc::new(ClouDNS(String::from_utf8(fernet.decrypt(prov_cfg.password.as_str()).unwrap()).unwrap()))); }
                    _ => { LoggerMessages::Error(LogErrors::DDnsUnk(name)).log(); }

                }
            }
        }

        drop(cfg);

        let mut ddns_services = self.ddns_services.write().await;
        *ddns_services = svc;

        Ok(())
    }
    pub async fn get_bind_addr(&self) -> SocketAddrV4
    {
        let cfg = self.config.lock().await;

        SocketAddrV4::new(
            cfg.daemon.host,
            cfg.daemon.port
        )
    }

    pub async fn get_net_counter(&self) -> NetIOCounter
    {
        let counter = self.net_counter.read().await;
        counter.clone()
    }

    pub async fn get_vpn_peers(&self) -> Result<Vec<VPNPeer>,HTTPMessage>
    {

        let mut cfg = self.config.lock().await;
        let mut wg_config = read_wireguard_config_file().await?;

        let mut peer_names = if let Some(v) = &cfg.networking.vpn.peers
        {
            v.iter().cloned().collect::<Vec<String>>()
        } else {Vec::new()};


        let wg_peers = wg_config
            .sections()
            .iter()
            .filter(|s| s.starts_with("peer"))
            .cloned()
            .collect::<Vec<String>>();


        let peers = std::iter::zip(&wg_peers, &peer_names).filter_map(
            |(cfg_section,name)|
                {
                    if let Some(ip) = wg_config.get(cfg_section.as_str(),"allowedips") &&
                        let Ok(ipv4) = Ipv4Net::from_str(ip.as_str())
                    {
                       Some(VPNPeer::new(name.clone(),ipv4.addr()))
                    }
                    else { None }
                }
        )
        .collect::<Vec<VPNPeer>>();

        println!("{} {}",peers.len(),wg_peers.len());

        //make the two list even in case they are not aligned anymore
        if peers.len() < peer_names.len()
        {
            peer_names.truncate(peers.len());
            cfg.networking.vpn.peers = if peer_names.len() == 0 {None} else {Some(peer_names)};
            drop(cfg);
            self.flush_config().await?;
        }
        else if peers.len() < wg_peers.len()
        {

            for i in  peers.len()..wg_peers.len()
            {

                let key = format!("peer@{}", i+1);
                wg_config.remove_section(key.as_str());
            }

            write_wireguard_config_file(wg_config).await?;
        }

        Ok(peers)
    }

    pub async fn get_ddns_providers(&self) -> Result<IndexMap<String,DDNSProvider>, HTTPMessage>
    {
        let cfg = self.config.lock().await;
        let mut providers:IndexMap<String,DDNSProvider> = IndexMap::new();
        for (name,prov_conf) in cfg.ddns.iter()
        {
            let prov_info = match prov_conf.downcast_ref::<Option<CfgDynDNS>>().unwrap()
            {
                Some(prov_info) => DDNSProvider::new
                (
                    prov_info.enabled,
                    prov_info.username.clone(),
                    Some(prov_info.last_update),
                    Some(prov_info.last_update + Duration::from_mins(cfg.get_ddns_refresh_time()).as_secs()),
                ),
                None => DDNSProvider::default(),
            };

            providers.insert(name.to_string(), prov_info);
        }

        Ok(providers)
    }

    pub async fn set_ddns_provider_credentials(&self, name:&str, username:Option<String>,password:String, enable:bool) -> Result<(),HTTPMessage>
    {
        let digest = Sha256::digest(self.secret_key.as_bytes());
        let key = URL_SAFE.encode(digest);
        let fernet = Fernet::new(key.as_str())
            .ok_or_else(|| ErrorMessages::E_NET_DDNS_CONFIG.wrap_with_status_code(None))?;

        let enc_password = fernet.encrypt(password.as_bytes());


        let mut cfg = self.config.lock().await;
        cfg.ddns_service_set_credential(name,username,enc_password,enable);
        drop(cfg);

        self.flush_config().await?;
        Ok(())
    }

    pub async fn enable_ddns_provider(&self, name:&str, enable:bool) -> Result<(),HTTPMessage>
    {
        let mut cfg = self.config.lock().await;
        cfg.ddns_service_set_enable(name,enable);
        drop(cfg);

        self.flush_config().await?;
        Ok(())
    }

    pub async fn iface_down(&self, iface:String) -> Result<(), HTTPMessage>
    {
        let mut cmds = vec![
          NMCLIDevice(IfaceStatusAction::Down.to_string().as_str(),Some(&vec![iface.as_str()]),CmdConfig::default())
        ];

        get_network_ifaces()
            .await
            .iter()
            .filter(|network| network.name != iface && network.enabled)
            .for_each(|network| {
                cmds.extend(vec![
                    NMCLIConnection(IfaceStatusAction::Down.to_string().as_str(),Some(&vec![network.name.as_str()]),CmdConfig::default()),
                    NMCLIConnection(IfaceStatusAction::Up.to_string().as_str(),Some(&vec![network.name.as_str()]),CmdConfig::default()),
                ])
            });

        Transaction::new(cmds)
            .execute()
            .await
            .map_err(|e| ErrorMessages::E_NET_CHANGE_STATE.wrap_with_status_code(
                Some(vec![Value::String(iface.clone()),Value::String(e.to_string())])
            ))?;

        LoggerMessages::Info(LogInfos::IfaceStatusChange(IfaceStatusAction::Down,iface.as_str())).log();

        let ctx = ContextBuilder::new()
            .push(ContextVariables::Iface,iface)
            .finish();

        self.event_manager.trigger(Trigger::Event(Events::IfaceDisabled),ctx).await;

        Ok(())
    }

    pub async fn iface_up(&self, iface:String) -> Result<(), HTTPMessage>
    {
        let cmds = vec![
            NMCLIDevice(IfaceStatusAction::Up.to_string().as_str(),Some(&vec![iface.as_str()]),CmdConfig::default())
        ];


        Transaction::new(cmds)
            .execute()
            .await
            .map_err(|e| ErrorMessages::E_NET_CHANGE_STATE.wrap_with_status_code(
                Some(vec![Value::String(iface.clone()),Value::String(e.to_string())])
            ))?;

        LoggerMessages::Info(LogInfos::IfaceStatusChange(IfaceStatusAction::Up,iface.as_str())).log();

        let ctx = ContextBuilder::new()
            .push(ContextVariables::Iface,iface)
            .finish();

        self.event_manager.trigger(Trigger::Event(Events::IfaceEnabled),ctx).await;

        Ok(())
    }

    pub async fn vpn_up(&self) -> Result<(), HTTPMessage>
    {
        let mut cmds = vec![
            Systemctl(
                self.get_vpn_service()
                    .await
                    .ok_or_else(||
                        ErrorMessages::E_NET_VPN_NOTCONF.wrap_with_status_code(None)
                    )?,
                SystemctlAction::Start,
                true,
                CmdConfig::default()
            )
        ];

        let firewall_cmd = Firewall(
            FirewallAction::State,
            false,
            false,
            CmdConfig::default()
        ).run().await;

        if let Ok(Some(output)) = firewall_cmd &&
            output.exit_code == 0 &&
            output.stdout.trim() == "running"
        {
            let wireguard_port = {
                let cfg = self.config.lock().await;
                cfg.networking.vpn.port
            };
            cmds.push(
                Firewall(FirewallAction::AddPort(
                    FirewallPort::Port(wireguard_port),
                    Protocol::UDP),
                         true,
                         true,
                         CmdConfig::default()
                )
            );

            cmds.push(Firewall(FirewallAction::Reload,false,false,CmdConfig::default()));
        }

        Transaction::new(cmds)
            .execute()
            .await
            .map_err(|e| ErrorMessages::E_NET_CHANGE_STATE.wrap_with_status_code(
                Some(vec![Value::String("VPN".to_string()),Value::String(e.to_string())])
            ))?;


        LoggerMessages::Info(LogInfos::IfaceStatusChange(IfaceStatusAction::Up,"VPN")).log();

        self.event_manager.trigger(Trigger::Event(Events::VPNEnabled),None).await;

        Ok(())
    }

    pub async fn vpn_down(&self) -> Result<(), HTTPMessage>
    {
        let mut cmds = vec![
            Systemctl(
                self.get_vpn_service()
                    .await
                    .ok_or_else(||
                        ErrorMessages::E_NET_VPN_NOTCONF.wrap_with_status_code(None)
                    )?,
                SystemctlAction::Stop,
                true,
                CmdConfig::default()
            )
        ];

        let firewall_cmd = Firewall(
            FirewallAction::State,
            false,
            false,
            CmdConfig::default()
        ).run().await;

        if let Ok(Some(output)) = firewall_cmd &&
            output.exit_code == 0 &&
            output.stdout.trim() == "running"
        {
            let wireguard_port = {
                let cfg = self.config.lock().await;
                cfg.networking.vpn.port
            };

            cmds.push(
                Firewall(FirewallAction::RemovePort(
                    FirewallPort::Port(wireguard_port),
                    Protocol::UDP),
                         true,
                         true,
                         CmdConfig::default()
                )
            );

            cmds.push(Firewall(FirewallAction::Reload,false,false,CmdConfig::default()));
        }

        Transaction::new(cmds)
            .execute()
            .await
            .map_err(|e| ErrorMessages::E_NET_CHANGE_STATE.wrap_with_status_code(
                Some(vec![Value::String("VPN".to_string()),Value::String(e.to_string())])
            ))?;


        LoggerMessages::Info(LogInfos::IfaceStatusChange(IfaceStatusAction::Down,"VPN")).log();

        self.event_manager.trigger(Trigger::Event(Events::VPNDisabled),None).await;

        Ok(())
    }

    pub async fn get_vpn_service(&self) -> Option<String>
    {
        let cfg = self.config.lock().await;

        cfg.systemd.iter().find(|s| s.starts_with("wg-quick")).cloned()
    }

    pub async fn is_vpn_active(&self) -> Result<bool, HTTPMessage>
    {
        let output = Systemctl(
            self.get_vpn_service()
                .await
                .ok_or_else(||
                    ErrorMessages::E_NET_VPN_NOTCONF.wrap_with_status_code(None)
                )?,
            SystemctlAction::Stop,
            true,
            CmdConfig::default())
            .run()
            .await
            .map_err(|e| propagate_error(ErrorMessages::E_NET_VPN_STATE,e))?
            .ok_or_else(|| ErrorMessages::E_NET_VPN_STATE.wrap_with_status_code(None))?;

        if output.exit_code == 0 || output.exit_code == 3
        {
            if output.stdout.contains("inactive") { Ok(false) } else { Ok(true) }
        }
        else
        {
            Err(ErrorMessages::E_NET_VPN_STATE.wrap_with_status_code(
                Some(vec![Value::String(output.stdout.clone())])
            ))
        }
    }

    pub async fn set_vpn_config(&self, address:Ipv4Addr,netmask: Ipv4Addr, endpoint:Ipv4Addr) -> Result<(), HTTPMessage>
    {
        let mut cfg = self.config.lock().await;
        cfg.networking.vpn.endpoint=Some(endpoint.clone());
        let wireguard_port = cfg.networking.vpn.port;
        drop(cfg);


        let wg_address = Ipv4Net::with_netmask(address,netmask)
            .map_err(|e| propagate_error(ErrorMessages::E_NET_INVALID_IP_ADDRESS,e))?;
        let wg_endpoint = format!("{}:{}",endpoint.to_string(),wireguard_port);

        let mut wg = read_wireguard_config_file().await?;

        wg.setstr("Interface","Address",Some(wg_address.to_string().as_str()));
        wg.setstr("Interface","listenport",Some(wireguard_port.to_string().as_str()));

        for section in wg.sections().iter().filter(|s| s.to_lowercase().starts_with("peer"))
        {
            wg.setstr(section,"endpoint",Some(wg_endpoint.as_str()));
        }

        write_wireguard_config_file(wg).await?;
        self.flush_config().await?;

        Systemctl(
            self.get_vpn_service().await.ok_or_else(||ErrorMessages::E_NET_VPN_NOTCONF.wrap_with_status_code(None))?,
            SystemctlAction::Restart,
            false,
            CmdConfig::default()
        ).run()
            .await
            .map_err(|e| propagate_error(ErrorMessages::E_NET_VPN_STATE,e))?
            .ok_or_else(|| ErrorMessages::E_NET_VPN_STATE.wrap_with_status_code(None))?
            .is_success()
            .map_err(|e| propagate_error(ErrorMessages::E_NET_VPN_STATE,e))?;

        LoggerMessages::Info(LogInfos::VPNConf).log();

        Ok(())
    }

    pub async fn get_vpn_endpoint(&self) -> Option<Ipv4Addr>
    {
        let cfg = self.config.lock().await;
        cfg.networking.vpn.endpoint.clone()
    }

    pub async fn vpn_genkeys(&self) -> Result<(), HTTPMessage>
    {

        // private key gen
        let cmd_genkey = WireGuard(WireGuardAction::GenPrivateKey,CmdConfig::Empty)
            .run()
            .await
            .map_err(|e|propagate_error(ErrorMessages::E_NET_VPN_GEN_PRIVATE,e))?
            .ok_or_else(|| ErrorMessages::E_NET_VPN_GEN_PRIVATE.wrap_with_status_code(None))?
            .is_success()
            .map_err(|e|propagate_error(ErrorMessages::E_NET_VPN_GEN_PRIVATE,e))?;

        let private_key = cmd_genkey.stdout.trim();
        let tmp_filename = "vpn_private.key";

        let mut tmp_fullpath = temp_dir();
        tmp_fullpath.push(tmp_filename);

        let mut handle = File::create(&tmp_fullpath)
            .await
            .map_err(|e|propagate_error(ErrorMessages::E_NET_VPN_GEN_PRIVATE,e))?;

        handle
            .write_all(private_key.as_bytes())
            .await
            .map_err(|e|propagate_error(ErrorMessages::E_NET_VPN_GEN_PRIVATE,e))?;

        MV(tmp_fullpath.to_str().unwrap(),VPN_PRIVATE_KEY,CmdConfig::default())
            .run()
            .await
            .map_err(|e|propagate_error(ErrorMessages::E_NET_VPN_GEN_PRIVATE,e))?;

        //public key gen
        let cfg_pubkey = CmdConfig::new(
            false,
            true,
            Some(format!("{}\n",private_key).as_bytes()),
            None
        );

        let cmd_genkey = WireGuard(WireGuardAction::GenPublicKey,cfg_pubkey)
            .run()
            .await
            .map_err(|e|propagate_error(ErrorMessages::E_NET_VPN_GEN_PUBLIC,e))?
            .ok_or_else(|| ErrorMessages::E_NET_VPN_GEN_PUBLIC.wrap_with_status_code(None))?
            .is_success()
            .map_err(|e|propagate_error(ErrorMessages::E_NET_VPN_GEN_PUBLIC,e))?;

        let tmp_filename = "vpn_public.key";

        let mut tmp_fullpath = temp_dir();
        tmp_fullpath.push(tmp_filename);

        let mut handle = File::create(&tmp_fullpath)
            .await
            .map_err(|e|propagate_error(ErrorMessages::E_NET_VPN_GEN_PUBLIC,e))?;

        handle
            .write_all(cmd_genkey.stdout.trim().as_bytes())
            .await
            .map_err(|e|propagate_error(ErrorMessages::E_NET_VPN_GEN_PUBLIC,e))?;

        MV(tmp_fullpath.to_str().unwrap(),VPN_PUBLIC_KEY,CmdConfig::default())
            .run()
            .await
            .map_err(|e|propagate_error(ErrorMessages::E_NET_VPN_GEN_PUBLIC,e))?;

        // change wg conf

        let mut wg_conf = read_wireguard_config_file().await?;
        wg_conf.setstr("Interface","PrivateKey",Some(private_key));
        write_wireguard_config_file(wg_conf).await?;



        Ok(())
    }

    pub async fn get_vpn_public_key(&self) -> Option<String>
    {
        let cmd = Cat(
            Some(VPN_PUBLIC_KEY),
            CmdConfig::default(),
        ).run()
        .await
        .unwrap_or(None);

        if let Some(output) = cmd
        {
            Some(output.stdout.trim().to_string())
        }
        else { None }
    }

    pub async fn add_vpn_peer(&self, name:&str, public_key:String) -> Result<(), HTTPMessage>
    {
        let mut cfg = self.config.lock().await;
        let name = name.trim();

        //dont want empty names or duplicates
        if name.len() == 0 || cfg.networking.vpn.peers.as_ref().unwrap_or(&Vec::new()).iter().find(|s| s.as_str() == name ).is_some()
        {
            return Err(ErrorMessages::E_NET_VPN_USER_INVALID.wrap_with_status_code(None));
        }

        if let Some(peers) = cfg.networking.vpn.peers.as_mut()
        {
            peers.push(name.to_string());
        }
        else
        {
            cfg.networking.vpn.peers = Some(vec![name.to_string()]);
        }

        let idx = cfg
            .networking
            .vpn
            .peers
            .as_ref()
            .unwrap() //this should be safe
            .len();


        let mut wg_conf = read_wireguard_config_file().await?;

        let vpn_address = wg_conf.get("Interface","Address")
            .ok_or_else(|| ErrorMessages::E_NET_VPN_NOTCONF.wrap_with_status_code(None))?
            .parse::<Ipv4Net>()
            .map_err(|e| propagate_error(ErrorMessages::E_NET_INVALID_NETMASK,e))?;


        let ip_prefix = vpn_address.prefix_len();
        let mut used_addresses = vec![vpn_address.addr()];

        let peer_endpoint = format!("{}:{}",used_addresses[0],cfg.networking.vpn.port);
        drop(cfg);

        for peer in wg_conf.sections().iter().filter(|s| s.to_lowercase().starts_with("peer"))
        {
            if let Ok(ip) = wg_conf.get(peer,"AllowedIPs").unwrap().parse::<Ipv4Net>()
            {
            used_addresses.push(ip.addr());
            }
        }

        let mut assigned_ip:Option<Ipv4Addr> = None;

        for host in vpn_address.hosts()
        {
            if !used_addresses.contains(&host)
            {
                assigned_ip = Some(host);
                break;
            }
        }

        if let Some(ip) = assigned_ip && let Ok(peer_ip) =Ipv4Net::new(ip,ip_prefix)
        {
            let section_name = format!("Peer@{}", idx);
            wg_conf.set(section_name.as_str(), "PublicKey", Some(public_key));
            wg_conf.set(section_name.as_str(), "AllowedIPs", Some(peer_ip.to_string()));
            wg_conf.setstr(section_name.as_str(), "PersistentKeepalive", Some("25"));
            wg_conf.set(section_name.as_str(), "Endpoint", Some(peer_endpoint));

            LoggerMessages::Info(LogInfos::VPNNewPeer(name.as_ref(),peer_ip.to_string().as_str())).log();
        }
        else
        {
            return Err(ErrorMessages::E_NET_VPN_IP_MAX.wrap_with_status_code(None));
        }



        self.flush_config().await?;
        write_wireguard_config_file(wg_conf).await?;

        Ok(())
    }

    pub async fn remove_vpn_peer(&self, name: &str) -> Result<(), HTTPMessage>
    {
        {
            let mut cfg = self.config.lock().await;
            if let Some(peers) = cfg.networking.vpn.peers.as_mut()
            {
                let idx = peers.iter().position(|s| s.as_str() == name );

                if let Some(pos) = idx
                {
                    peers.retain(|p| p.as_str() != name);

                    let mut wg_conf = read_wireguard_config_file().await?;

                    wg_conf.remove_section(format!("Peer@{}", pos+1).as_str());
                    write_wireguard_config_file(wg_conf).await?;
                }
            }
        }

        self.flush_config().await?;

        Ok(())

    }

}

// Auth-related Methods
impl Backend
{
    //verify if a token is valid
    pub async fn verify_token(&self, token:&str,requested_purpose:TokenPurposes) -> Result<JWTClaim, HTTPMessage>
    {
        let claims = token_verification(token, requested_purpose, self.secret_key.as_bytes())?;

        let cfg = self.config.lock().await;

        if !cfg.is_token_issued(&claims.uuid)
        {
            return Err(ErrorMessages::E_AUTH_REVOKED.wrap_with_status_code(None));
        }

        Ok(claims)
    }

    //Add a new JWT token to the configuration file
    pub async fn push_token(self:&Arc<Self>, token:JWTClaim)
    {
        let mut cfg = self.config.lock().await;
        cfg.approve_token(token.uuid, token.claims);
    }

    //Revoke a JWT token given its uuid
    pub async fn revoke_token(&self, uuid:&String)
    {
        let mut cfg = self.config.lock().await;
        cfg.revoke_token(&uuid);
    }

    //return true if all of the admin users has no configured secrets (ie first boot)
    pub async fn is_otp_configured(&self) -> bool
    {
        let users = self.users.lock().await;
        let cfg = self.config.lock().await;
        let mut configured = false;

        for user in users.iter()
        {
            let u = user.read().await;
            if u.admin
            {
                if let Some(u) = cfg.get_user(&u.username)
                {
                    if u.otp_secret.is_some()
                    {
                        configured = true;
                        break;
                    }
                }
            }
        }
        return configured;
    }

    pub async fn has_otp_secret(&self,username:&String) -> bool
    {
        let cfg = self.config.lock().await;
        if let Some(user) = cfg.get_user(username)
        {
            return user.otp_secret.is_some();
        }
        return false;
    }

    pub async fn add_temporary_secret(&self,username:Option<String>,secret:String)
    {
        let mut secrets = self.tmp_secrets.lock().await;
        let uuid = Uuid::new_v4();
        secrets.insert(uuid.to_string(),TemporarySecret { uuid: uuid.to_string(), username, secret });
    }

    pub async fn get_temporary_secrets(&self) -> Vec<TemporarySecret>
    {
        let tmp_secrets = self.tmp_secrets.lock().await;
        tmp_secrets.values().cloned().collect()
    }

    pub async fn save_temporary_secret(&self,uuid:&String) -> Result<String, HTTPMessage>
    {
        let is_otp_configured = self.is_otp_configured().await; //moved here to avoid deadlocks

        let mut secrets = self.tmp_secrets.lock().await;
        let secret = match secrets.get(uuid)
        {
            Some(s) => s,
            None => {
                LoggerMessages::Warning(LogWarnings::TmpSecretNotFound(uuid)).log();
                return Err(ErrorMessages::E_AUTH_INVALID.wrap_with_status_code(None));
            }
        };


        let mut cfg = self.config.lock().await;

        // this happens for a new user or a user has reset their credentials
        if let Some(username) = &secret.username
        {
            let u = cfg.users.get_mut(username);
            match u
            {
                Some(user) =>
                {
                    let tmp_sec = secrets.remove(uuid).unwrap();
                    user.otp_secret = Some(tmp_sec.secret);
                    return Ok(tmp_sec.username.unwrap());
                }
                None => return Err(ErrorMessages::E_USER_NOT_FOUND.wrap_with_status_code(None))

            }
        }
        else //this happens when no admin has access (eg first time boot)
        {
            if !is_otp_configured
            {
                for u in self.get_admin_users().await
                {
                    let usr = u.read().await;

                    if let Some(cfg_u) = cfg.users.get_mut(&usr.username)
                    {
                        if cfg_u.otp_secret.is_none()
                        {
                            let tmp_sec = secrets.remove(uuid).unwrap();
                            cfg_u.otp_secret = Some(tmp_sec.secret);

                            LoggerMessages::Info(LogInfos::OTPSecretConf(&usr.username)).log();
                            return Ok(usr.username.clone())
                        }
                    }
                }
            }

            LoggerMessages::Error(LogErrors::AdminOTPAlreadyConf).log();
            return Err(ErrorMessages::E_AUTH_ALREADY_CONFIG.wrap_with_status_code(None));
        }
    }

    //Return a vec of tuple containing (<username>,<secret>)
    pub async fn get_otp_secrets(&self) -> Vec<(String,String)>
    {
        let cfg = self.config.lock().await;

        let mut user_secrets: Vec<(String, String)> = Vec::new();

        for (uname, cfg_u) in &cfg.users
        {
            if let Some(secret) = &cfg_u.otp_secret
            {
                user_secrets.push((uname.clone(), secret.clone()));
            }
        }

        user_secrets
    }
}


// Pool-related Methods
impl Backend
{
    //Return quota information for all users
    pub async fn get_quota_info(&self,log:bool) -> Option<HashMap<String,Quota>>
    {
        if self.is_mounted().await
        {
            let cfg = self.config.lock().await;

            if let Some(pool) = &cfg.pool
            {
                match get_quota_for_all(&pool.name, &pool.dataset).await
                {
                    Ok(map) => { return Some(map); }
                    Err(e) => {
                        if log { LoggerMessages::Warning(LogWarnings::ZfsQuota(&e)).log(); }
                    }
                }
            } else {
                if log { LoggerMessages::Warning(LogWarnings::ZfsQuotaNoPool).log(); }
            }
        }

        None
    }

    //If a pool is configured, return a tuple with (<pool name>, <dataset name>); None otherwise
    pub async fn get_pool_identifier(&self) -> Option<(String,String)>
    {
        let cfg = self.config.lock().await;

        if let Some(pool) = &cfg.pool
        {
            return Some((pool.name.clone(),pool.dataset.clone()));
        }

        None
    }

    //Returns true if the pool is mounted
    pub async fn is_mounted(&self) -> bool
    {
        self.mount.read().await.as_ref().is_some()
    }


    //Return the mountpoint where the pool is mounted, None otherwise
    pub async fn mountpoint(&self) -> Option<PathBuf>
    {
        if self.is_mounted().await
        {
            let mp = self.mount.read().await;
            if let Some(vfs) = mp.as_ref()
            {
                return Some(vfs.basepath());
            }

        }

        None
    }

    //Returns true if the backend has a pool configured
    pub async fn is_pool_configured(&self) -> bool
    {
        self.get_pool_identifier().await.as_ref().is_some()
    }

    pub async fn is_pool_present(&self) -> bool
    {
        if let Some((pool_name,_)) = self.get_pool_identifier().await
        {
            if let Ok(output_result) = ZPool(
                ZPoolActions::Status(pool_name),
                false,CmdConfig::Empty).run().await && let Some(output) = output_result
            {
                return output.is_success().is_ok();
            }
        }

        false
    }

    //Return any msgid in the pool status (if any)
    pub async fn get_pool_status_id(&self) -> Option<String>
    {
        if let Some((pool_name,_)) = self.get_pool_identifier().await
        {
            if let Ok(output_result) = ZPool(
                ZPoolActions::Status(pool_name.clone()),
                false,CmdConfig::Empty
            )
            .run().await && let Some(output) = output_result
            {
                if output.exit_code == 0
                {
                    let status:Value = serde_json::from_str(&output.stdout)
                        .or(serde_json::from_str("{}"))
                        .unwrap();

                    match &status["pools"][pool_name]["msgid"]
                    {
                        Value::String(id) => return Some(id.to_string()),
                        _ => ()
                    }
                }
            }           
        }

        None
    }

    async fn is_any_pool_present(self:&Arc<Self>) -> bool
    {

        if let Ok(output_result) = ZFS(
            ZFSActions::List(
                ZFSListArgs::new_with_no_args(Some(ZFSListType::Filesystem), None)
            ), 
            false,CmdConfig::Empty).run().await && let Some(output) = output_result
        {
            if output.exit_code == 0
            {
                if let Ok(zfs_list) = serde_json::from_str::<Value>(&output.stdout)
                {
                    let datasets = &zfs_list["datasets"];
                    if datasets.is_object()
                    {
                        return datasets.as_object().iter().len()>0;
                    }
                }
            }
        }

        return false;
    }


    //Return the capacity of a pool
    pub async fn pool_capacity(&self) -> Result<Option<Capacity>, HTTPMessage>
    {
        let vfs = self.mount.read().await;

        match vfs.as_ref()
        {
            Some(v) => Ok(Some(v.capacity.clone())),
            None => Ok(None)
        }
    }

    // Returns the progression status of a pool expansion (ie when a new disk is added to a pool)
    pub async fn get_expansion_status(&self) -> Result<PoolExtensionStatus, HTTPMessage>
    {
        let pool_id = self.get_pool_identifier().await;
        if pool_id.is_none()
        {
            return Err(ErrorMessages::E_POOL_NO_CONF.wrap_with_status_code(None));
        } 

        if !self.has_redundancy().await
        {
            return Ok(PoolExtensionStatus::new(false,None,None));
        }

        let pool_name = pool_id.unwrap().0;

        if let Ok(output_result) = ZPool(
            ZPoolActions::Status(pool_name),
            false,
            CmdConfig::Empty
        ).run().await && let Some(output) = output_result
        {
            if output.exit_code != 0
            {
                return Err(ErrorMessages::E_POOL_EXPAND_STATUS.wrap_with_status_code(Some(vec![Value::String(output.stderr)])));
            }

            let msg = output.stdout;


            //Case 1: percentage + ETA Available
            let re_with_eta = RegexBuilder::new(r"([\d.]+)%\s+done,\s+([\d:]+)\s+to\s+go")
                              .case_insensitive(false)
                              .build()
                              .map_err(|e| propagate_error(ErrorMessages::E_POOL_EXPAND_STATUS, e))?;
            
            if let Some(m) = re_with_eta.captures(&msg)
            {
                let perc:f32 = m[1]
                                .parse::<f32>()
                                .map_err(|e| propagate_error(ErrorMessages::E_POOL_EXPAND_STATUS, e))?;

                let time:Vec<&str> = m[2].split(":").collect();

                return Ok(
                    PoolExtensionStatus { 
                        is_running: true, 
                        eta: {
                            if time.len() ==3
                            {
                                let h = time[0].parse::<i64>().unwrap();
                                let m = time[1].parse::<i64>().unwrap();
                                let s = time[2].parse::<i64>().unwrap();

                                let d = TimeDelta::hours(h) + TimeDelta::minutes(m) + TimeDelta::seconds(s);

                                Some(d.num_seconds())

                            }
                            else { None }
                        }, 
                        progress: Some(perc)
                    }
                );
            }

            //CASE 2: percentace + no ETA
            let re_no_eta = RegexBuilder::new(r"([\d.]+)%\s+done,.*no\s+estimated\s+time")
                              .case_insensitive(false)
                              .build()
                              .map_err(|e| propagate_error(ErrorMessages::E_POOL_EXPAND_STATUS, e))?;

            if let Some(m) = re_no_eta.captures(&msg)
            {
                let perc:f32 = m[1].parse::<f32>().map_err(|e| propagate_error(ErrorMessages::E_POOL_EXPAND_STATUS, e))?;

                return Ok(
                    PoolExtensionStatus { is_running: true, eta: None, progress: Some(perc) }
                );
            }

            //CASE 3: completed
            let re_completed = RegexBuilder::new(r"expand:\s+expanded")
                              .case_insensitive(false)
                              .build()
                              .map_err(|e| propagate_error(ErrorMessages::E_POOL_EXPAND_STATUS, e))?;
            if re_completed.is_match(&msg)
            {
                return Ok(
                    PoolExtensionStatus { is_running: false, eta: None, progress: Some(100.0) }
                );
            }

            Ok(
                    PoolExtensionStatus { is_running: true, eta: None, progress: None }
            )

        }
        else 
        {
            Err(ErrorMessages::E_POOL_EXPAND_STATUS.wrap_with_status_code(
                Some(
                    vec![Value::String("Failed to start zfs pool".to_string())]
                    )
                )
            )    
        }
    }

    pub async fn get_importable_pools(&self) -> Result<Vec<Pool>, HTTPMessage>
    {
        let zpool_output = ZPool(
            ZPoolActions::Import(None),
        false,
            CmdConfig::default()
        )
        .run()
        .await
        .map_err(
            |e| propagate_unknown_error(e)
        )?
        .unwrap()
        .is_success()
        .map_err(|e| propagate_unknown_error(e))?;

        let mut current_pool:Option<Pool> = None;
        let mut pools:Vec<Pool> = Vec::new();
        let mut in_config:bool = false;
        let mut read_status_action:bool = false;

        let pool_re = RegexBuilder::new(r"\s*pool:\s+(\S+)")
                                    .case_insensitive(true)
                                    .build()
                                    .unwrap();

        let disk_re = RegexBuilder::new(r"(\S+)\s+(ONLINE|DEGRADED|FAULTED|OFFLINE|UNAVAIL)")
                            .case_insensitive(true)
                            .build()
                            .unwrap();

        let skip_vdev_re = RegexBuilder::new(r"(mirror|raidz)\S*")
                                .case_insensitive(true)
                                .build()
                                .unwrap();
        

        for line in zpool_output.stdout.lines()
        {
            let l = line.trim();

            if let Some(m) = pool_re.captures(l)
            {
                if let Some(p) = current_pool
                {
                    pools.push(p);
                }

                current_pool = Some(
                    Pool 
                    { 
                        name: m[1].to_string(), 
                        disks: Vec::new(), 
                        message: Some(String::new()), 
                        state: None
                    }
                );
                continue;
            }

            if l=="config:"
            {
                in_config=true;
                read_status_action=false;
                continue;
            }

            if let Some(pool) = &mut current_pool
            {

                if l.starts_with("status:") || l.starts_with("action:")
                {
                    
                    read_status_action = true;
                    let tok:Vec<&str> = l.split(":").collect();
                    if tok.len() == 2
                    {
                        if let Some(message) = pool.message.as_mut()
                        {
                            message.push_str(" ");
                            message.push_str(tok[1].trim());
                        }
                    }
                    continue;
                }
                else if read_status_action
                {
                    if l.len()>0
                    {
                        if let Some(message) = pool.message.as_mut()
                        {
                            message.push_str(" ");
                            message.push_str(l.trim());
                        }          
                    }
                    continue;
                }
            

                if l.starts_with("state:")
                {
                    let tok:Vec<&str> = l.split(":").collect();
                    if tok.len() == 2
                    {
                        pool.state = Some(tok[1].trim().to_string());   
                    }
                    continue;
                }

                if !in_config { continue; }

                if let Some(d) = disk_re.captures(l)
                {
                    let dev = d[1].trim();
                    let state = d[2].trim();

                    if !skip_vdev_re.is_match(dev) && (dev!=pool.name)
                    {
                        pool.disks.push( 
                            Device::from_subpath(
                                dev,
                                DiskState::from_str(state).map_err(|e| propagate_unknown_error(e))?
                            ).await
                            .or_else
                            (
                                |_| Ok(Device::new_offline(dev))
                            )?
                        )
                    }

                }
            }

        }

        if let Some(p) = current_pool // this can happen for the last one (e.g., when there's just one)
        {
            pools.push(p);
        }

        return Ok(pools);
                
    }


    //Returns true if the pool has redundancy enabled, false if not or if no pool is configured
    pub async fn has_redundancy(&self)->bool
    {
        let pool_props_mg = self.pool_properties.read().await;

        match pool_props_mg.as_ref()
        {
            Some(p) => p.redundancy,
            None => false
        }
    }

    //Returns true if the pool has encryption enabled, false if not or if no pool is configured
    pub async fn has_encryption(&self)->bool
    {
        let pool_props_mg = self.pool_properties.read().await;

        match pool_props_mg.as_ref()
        {
            Some(p) => p.encryption,
            None => false
        }
    }

    //Returns true if the pool has compression enabled, false if not or if no pool is configured
    pub async fn has_compression(&self)->bool
    {
        let pool_props_mg = self.pool_properties.read().await;

        match pool_props_mg.as_ref()
        {
            Some(p) => p.compression,
            None => false
        }
    }

    //Returns the pool encryption key in base64 encoding
    pub async fn get_key(&self)->Result<Option<String>, HTTPMessage>
    {
        if self.has_encryption().await
        {
            let cfg = &self.config.lock().await;
            let cfg_pool = &cfg.pool;

            if let Some(pool) = cfg_pool
            {
                if let Some(key_path) = &pool.encryption_key
                {
                    let mut cat = Cat(
                        Some(key_path),
                        CmdConfig::default()
                    )
                    .spawn()
                    .map_err(|e| propagate_error(ErrorMessages::E_POOL_KEY, e))?;


                    cat.wait().await.map_err(|e| propagate_error(ErrorMessages::E_POOL_KEY, e))?;


                    let mut key_buffer: Vec<u8> = Vec::new();

                    match cat.stdout.as_mut()
                    {
                        None => return Err(ErrorMessages::E_POOL_KEY.wrap_with_status_code(None)),
                        Some(stdout) => { stdout.read_to_end(&mut key_buffer).await.map_err(|e| propagate_error(ErrorMessages::E_POOL_KEY, e))?; }

                    }

                    return Ok(Some(BASE64_STANDARD.encode(key_buffer)));
                }
            }
        }
        Ok(None)
    }


    async fn update_scrub_details(&self)
    {
        let pool_id = self.get_pool_identifier().await;
        if let Some((pool_name,_)) = pool_id
        {
            let zpool_output = ZPool(
                ZPoolActions::Status(pool_name.clone()),
                false, 
                CmdConfig::default()
            ).run().await;

            if let Ok(r) = zpool_output && let Some(output) = r && output.exit_code == 0
            {
                let m:Value = serde_json::from_str(&output.stdout).or::<Value>(Ok(Value::Null)).unwrap();

                if let Value::Object(scan_stats) = &m["pools"][pool_name.clone()]["scan_stats"]
                {
                    if let Some(function) = scan_stats["function"].as_str() && function == "SCRUB"
                    {
                        let mut scrub_details = self.scrub_details.write().await;
                        (*scrub_details).last_scrub_report = Some(LastScrubReport::new(
                            str_to_i64(scan_stats["start_time"].as_str()),
                            str_to_i64(scan_stats["end_time"].as_str()),
                            scan_stats["errors"].as_str(),
                        ));
                    }
                }

                if let Value::Object(scan_stats) = &m["pools"][pool_name]["scan_stats"]
                {
                    let ongoing: bool = scan_stats["function"].as_str().unwrap() == "SCANNING";
                    let time:Option<i64> = {
                        if ongoing { None }
                        else if let Some(int) = str_to_i64(scan_stats["end_time"].as_str())
                        {
                            if int > 0 { Some(int) }
                            else {None}
                        }
                        else {str_to_i64(scan_stats["start_time"].as_str())}
                    };

                    let mut scrub_details = self.scrub_details.write().await;
                    (*scrub_details).scrub_live_info = Some( ScrubLiveInfo::new(ongoing, time));
                }
            }
        }
    }

    pub async fn get_last_scrub_report(&self) -> Option<LastScrubReport>
    {
        self.scrub_details.read().await.last_scrub_report.clone()
    }
    pub async fn get_current_scrub_info(&self) -> Option<ScrubLiveInfo>
    {
        self.scrub_details.read().await.scrub_live_info.clone()
    }

    pub async fn start_scrub(self:&Arc<Self>) -> Result<Uuid, HTTPMessage>
    {
        if let Some((pool_name, _)) = self.get_pool_identifier().await
        {
            ZPool(ZPoolActions::Scrub(pool_name.clone()),false,CmdConfig::default())
                .run()
                .await
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_SCRUB, e))?
                .ok_or(ErrorMessages::E_POOL_SCRUB.wrap_with_status_code(None))?
                .is_success()
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_SCRUB, e))?;

            let backend = Arc::clone(&self);
            let scrub_task = Arc::new(
                BackgroundTask::new(
                    Box::new(move |_| {
                        let pool_name = pool_name.clone();
                        let b = Arc::clone(&backend);

                        Box::pin(async move {
                            loop {
                                sleep(Duration::from_secs(2)).await;

                                let output = ZPool(ZPoolActions::Status(pool_name.clone()),false,CmdConfig::Empty)
                                   .run()
                                   .await;

                                match output
                                {
                                    Ok(result) => {
                                        if let Some(o) = result && o.exit_code == 0
                                        {
                                            if let Ok(v) = serde_json::from_str::<Value>(&o.stdout) && let Some(d) = v.as_object()
                                            {
                                                let scan_stats = &d["pools"][pool_name.clone()]["scan_stats"];

                                                if let Some(scan_stats) = scan_stats.as_object()
                                                {
                                                    if let Some(function) = scan_stats["function"].as_str() && function == "SCRUB"
                                                    {
                                                        if let Some(state) = scan_stats["state"].as_str() && state == "FINISHED"
                                                        {
                                                            break;
                                                        }
                                                    }

                                                }
                                            }

                                        }
                                        else
                                        {
                                            return  Err(anyhow![ErrorMessages::E_POOL_SCRUB.wrap(None)]);
                                        }
                                    }
                                    Err(err) => return Err(anyhow![
                                        ErrorMessages::E_POOL_SCRUB.wrap(Some(vec![Value::from(err.to_string())])),
                                    ])
                                }
                            }

                            b.update_scrub_details().await;

                            Ok(SuccessMessages::S_POOL_SCRUB)
                        })
                    }),
                 Some("Scrub Task".to_string())
                )
            );

            return Ok(self.background_task_manager.add_task(scrub_task).await);
        }

        Err(ErrorMessages::E_POOL_NO_CONF.wrap_with_status_code(None))
    }



    pub async fn get_pool_snapshots(&self) -> Vec<Snapshot>
    {
        let snapshots = self.snapshots.read().await;
        snapshots.clone()
    }

    // Returns the disk devices in the zfs pool
    pub async fn get_pool_disks(&self) -> Vec<Device>
    {
        let is_configured = self.is_pool_configured().await;
        if is_configured
        {
            let pool_props = self.pool_properties.read().await;
            if  let Some(props) = pool_props.as_ref()
            {
                return props.attached_disks.clone();
            }
        }

        Vec::new()
    }



    pub async fn mount(&self,user:Option<&User>) -> Result<(), HTTPMessage>
    {
        {
            let cfg = self.config.lock().await;
            if let Some(pool) = &cfg.pool
            {
                if !self.is_mounted().await
                {
                    let mut cmds: Vec<CommandLine> = Vec::new();

                    if let Some(key_path) = &pool.encryption_key
                    {
                        cmds.push(
                            ZFS(
                                ZFSActions::LoadKey(
                                    ZFSLoadKeyArgs {
                                        pool: pool.name.clone(),
                                        key_path: key_path.clone(),
                                    }
                                ),
                                true,
                                CmdConfig::Provided {
                                    sudo: true,
                                    strict: false, // sometimes the key can be already loaded and this will result in an error
                                    stdin: None,
                                    cwd: None,
                                },
                            )
                        )
                    }

                    cmds.push(ZFS(ZFSActions::Mount(
                        ZFSArgs {
                            pool: pool.name.clone(),
                            dataset: None,
                        }
                    ), true, CmdConfig::default()));

                    cmds.push(ZFS(ZFSActions::Mount(
                        ZFSArgs {
                            pool: pool.name.clone(),
                            dataset: Some(pool.dataset.clone()),
                        }
                    ), true, CmdConfig::default()));

                    Transaction::new(cmds)
                        .accept_error_if(stderr_contains("filesystem already mounted"))
                        .execute()
                        .await
                        .map_err(|e| propagate_error(ErrorMessages::E_POOL_MOUNT, e))?;
                }

                let mut ctx = ContextBuilder::new();

                if let Some(u) = user
                {
                    ctx = ctx.push(ContextVariables::TriggerUser,u.username.clone());
                }

                self.event_manager.trigger(Trigger::Event(Events::PoolMount),ctx.finish()).await;
            }
            else
            {
                return Err(ErrorMessages::E_POOL_NO_CONF.wrap_with_status_code(None));
            }
        }


        Ok(())
    }

    pub async fn unmount(&self, user:Option<&User>) -> Result<(), HTTPMessage>
    {
        let services = get_remote_services()
            .await
            .map_err(|e| propagate_error(ErrorMessages::E_POOL_UNMOUNT, e))?;

        for s in services.iter()
        {
            let mut service = s.write().await;
            let service_name = service.service_name().await;
            if service_name != "ssh" //SSH is special - if we disable it we'll lose the possibility to restore the system if needeed (already happened!)
            {
                if service.is_active().await.unwrap_or(true)
                {
                    service.stop()
                        .await
                        .map_err(|e| propagate_error(ErrorMessages::E_POOL_UNMOUNT, e))?;

                    LoggerMessages::Warning(LogWarnings::RemoteServiceStopped(service_name, None)).log();
                }
            }
        }

        let cfg = self.config.lock().await;
        if let Some(pool) = &cfg.pool && self.is_mounted().await
        {
            let mut cmds:Vec<CommandLine> = Vec::new();

            cmds.push(ZFS(ZFSActions::Unmount(
                ZFSArgs {
                    pool: pool.name.clone(),
                    dataset: Some(pool.dataset.clone())
                }
            ), true, CmdConfig::default()));

            cmds.push(ZFS(ZFSActions::Unmount(
                ZFSArgs {
                    pool: pool.name.clone(),
                    dataset: None
                }
            ), true, CmdConfig::default()));


            if self.has_encryption().await
            {
                cmds.push(
                    ZFS(
                        ZFSActions::UnloadKey(
                            pool.name.clone()
                        ),
                        true,
                        CmdConfig::Provided {
                            sudo: true,
                            strict: false, // sometimes the key can be already loaded and this will result in an error
                            stdin: None,
                            cwd: None
                        }
                    )
                )
            }


            Transaction::new(cmds)
                .execute()
                .await
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_UNMOUNT, e))?;

        }

        let mut ctx = ContextBuilder::new();

        if let Some(u) = user
        {
            ctx = ctx.push(ContextVariables::TriggerUser,u.username.clone());
        }

        self.event_manager.trigger(Trigger::Event(Events::PoolUnmount),ctx.finish()).await;

        Ok(())
    }

    pub async fn export_pool(&self, user: Option<&User>) -> Result<(), HTTPMessage>
    {

        if let Some((pool_name,_)) = self.get_pool_identifier().await
        {
            self.unmount(user).await?;

            ZPool(ZPoolActions::Export(pool_name),false,CmdConfig::default())
                .run()
                .await
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_DETACH,e))?
                .ok_or_else(|| propagate_unknown_error(anyhow!("unable to export pool")))?
                .is_success()
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_DETACH,e))?;

            self.deinit_pool().await;
            self.flush_config().await?;

        }
        else {return Err(ErrorMessages::E_POOL_NO_CONF.wrap_with_status_code(None));}

        Ok(())
    }

    pub async fn import_pool(&self, pool_name:&str, load_key:bool, user: Option<&User>) -> Result<(), HTTPMessage>
    {
        if self.is_pool_configured().await
        {
            return Err(ErrorMessages::E_POOL_CONFIG.wrap_with_status_code(None));
        }

        let mut cmds: Vec<CommandLine> = vec![ZPool(ZPoolActions::Import(
            Some(ZPoolImportArgs {
                pool: pool_name.to_string(),
                force: true
            })),true,CmdConfig::default()
        )];

        if load_key
        {
            cmds.push(
                ZFS(
                    ZFSActions::LoadKey(
                        ZFSLoadKeyArgs{
                            pool: pool_name.to_string(),
                            key_path: POOL_KEY_PATH.to_string()
                        }),
                    true, CmdConfig::default()
                    )
                );
        }

        Transaction::new(cmds)
            .execute()
            .await
            .map_err(|e| propagate_error(ErrorMessages::E_POOL_ATTACH,e))?;

        self.configure_pool().await?;
        self.mount(user).await?;
        self.flush_config().await?;


        Ok(())
    }

}

//Device-related Methods
impl Backend
{
    //Get disks attached to the system linking their states with the ZFS pool
    pub async fn get_disks(&self) -> Vec<Device>
    {

        let mut pool_disks = self.get_pool_disks().await;
        let mut system_disks = get_system_disks().await;

        let mut detected_disks:Vec<Device> = Vec::new();

        for sysdisk in system_disks.iter()
        {
            for pooldisk in pool_disks.iter()
            {
                if sysdisk == pooldisk
                {
                    detected_disks.push(pooldisk.clone());
                }
            }
        }

        pool_disks.retain(|v| !detected_disks.contains(v));
        system_disks.retain(|v| !detected_disks.contains(v));

        detected_disks.extend(pool_disks);
        detected_disks.extend(system_disks);

        detected_disks.sort_by_key(|a| a.name.clone() );

        return detected_disks;
        
    }
}

// Remote access services-related Methods

impl Backend
{
    pub async fn trigger_remote_access_services_permissions(username:&str, permissions:Option<&Vec<String>>,user_deleted:bool) -> Result<(), anyhow::Error>
    {
        for svc in get_remote_services().await?
        {
            let service = svc.read().await;
            if let Some(hooks) = service.permission_hooks()
            {
                if !user_deleted
                {
                    if let Some(perms) = permissions && hooks.get_trigger_permissions().await.iter().all(|p| p.is_any_allowed(perms))
                    {
                        hooks.permission_granted(username).await;
                    } else
                    {
                        hooks.permission_revoked(username).await;
                    }
                }
                else
                {
                    hooks.user_deleted(username).await;
                }
            }
        }
        Ok(())
    }

    pub async fn access_service_change_password(&self, service_name: &str, username:&str, password:&str) -> Result<(), HTTPMessage>
    {
        let services = get_remote_services()
            .await
            .map_err(|e| propagate_error(ErrorMessages::E_USER_PASSWD,e))?;

        let mut svc:Option<&AbstractRemoteService> = None;

        for s in services.iter()
        {
            let curr_serv_name = s.read().await.service_name().await;
            if  curr_serv_name == service_name
            {
                svc=Some(s);
                break;
            }
        }

        if let Some(service) = svc && let Some(auth) = service.read().await.auth()
        {
            auth.change_password(username, password).await
                .map_err(|e| propagate_error(ErrorMessages::E_USER_PASSWD,e))?;
        }
        else
        {
            return Err(ErrorMessages::E_ACCESS_SERV_UNK.wrap_with_status_code(Some(vec![Value::String(service_name.to_string())])) );
        }



        Ok(())
    }
}

// User-related Methods
impl Backend
{
    // Update partial information of each users, such as quota and notification count
    async fn update_users(self:&Arc<Self>)
    {
        let mut quota_info = self.get_quota_info(false).await;

        if let Some(map) = &mut quota_info
        {
            let users = self.users.lock().await;
            for u in users.iter()
            {
                let mut user = u.write().await;
                user.quota = map.remove(&user.username);
                user.notifications = get_notifications_count(&user.username).await;
            }
        }
    }

    // Reload all the User structs
    pub async fn reload_users(&self)
    {
        let mut users = self.users.lock().await;
        let quota_info = self.get_quota_info(true).await;


        let mut cfg = self.config.lock().await;
        users.clear();

        let mut tokens_uuid_to_revoke:Vec<String> = Vec::new();
        let mut token_to_approve:Option<(String, CfgToken)> = None;

        for (uname, prop) in &cfg.users
        {
            //quota detection
            let quota:Option<Quota> = match quota_info
            {
                Some(ref map) => match map.get(uname)
                    {
                        Some(opt) => Some(opt.clone()),
                        None=> None
                    }
                _ => None
            };

            let mut sudo:bool = false;

            let uname_ref = Some(uname.as_str());


            let groups_result = Groups(uname_ref.unwrap(),CmdConfig::default()).run().await;
            if let Ok(r) = groups_result && let Some(group_output) = r && (group_output.exit_code == 0)
            {
                if let Some(_) = group_output.stdout.find(sudo_group())
                {
                    sudo = true;
                }
            }

            //first token
            let mut home_dir:Option<String> = None;
            let mut uid:Option<u32> = None;
            let mut gid:Option<u32> = None;

            //get home - uid - gid
            let getentpasswd_result  = GetEntPasswd(uname_ref, CmdConfig::default()).run().await;

            if let Ok(r) = getentpasswd_result && let Some(output) = r && output.exit_code == 0
            {
                let tokens:Vec<&str> = output.stdout.split(":").collect();

                if tokens.len()>5
                {
                    uid = Some(tokens[2].parse::<u32>().unwrap());
                    gid = Some(tokens[3].parse::<u32>().unwrap());
                    home_dir = Some(tokens[5].to_string());
                }
            }

            let user=
                User{
                    username: uname.to_string(),
                    visible_name: prop.fullname.clone(),
                    permissions: prop.permissions.clone(),
                    quota,
                    sudo,
                    admin: {
                        match &prop.permissions
                        {
                            Some(perms) => is_admin(&perms),
                            None => false
                        }
                    },
                    first_login_token: {
                        if prop.otp_secret.is_some() { None }
                        else
                        {
                            let previous_issued_tokens = cfg.find_tokens_by_purpose(TokenPurposes::FirstLogin, Some(uname));

                            if previous_issued_tokens.len() == 0
                            {
                                //need to create a new token to avoid that the user gets locked out
                                let t = create_token(
                                    Some(uname.to_string()),
                                    TokenPurposes::FirstLogin,
                                    60*60*24, //24 hours
                                    self.secret_key.as_bytes()
                                );

                                match t
                                {
                                    Ok(tok) => {
                                        token_to_approve = Some((tok.uuid.clone(),tok.claims));
                                        Some(tok.uuid)
                                    }
                                    Err(e) => {
                                        LoggerMessages::Error(LogErrors::FirstLoginToken(uname, &e.to_string())).log();
                                        None
                                    }
                                }
                            }
                            else
                            {
                                //if more tokens are found as first login token for this user, issue the most recent one and revoke the others.
                                let mut vectorised_prev_tokens:Vec<(&String,&CfgToken)> = Vec::new();

                                for (k,v) in &previous_issued_tokens
                                {
                                    vectorised_prev_tokens.push((&k,&v));
                                }

                                vectorised_prev_tokens.sort_by(
                                    |(_,a), (_,b)| {
                                    b.exp.cmp(&a.exp)
                                });

                                let tokes_to_revoke = &vectorised_prev_tokens[1..];

                                for (uuid,_) in tokes_to_revoke.iter()
                                {
                                    tokens_uuid_to_revoke.push(uuid.to_string());
                                }

                                Some(vectorised_prev_tokens[0].0.clone())
                            }
                        }
                    },
                    home_dir: {
                        match home_dir
                        {
                            Some(p) => Some(Path::new(&p).to_path_buf()),
                            None => None
                        }
                    },
                    uid: uid,
                    gid:gid,
                    notifications:get_notifications_count(uname).await
                };

            users.push(Arc::new(RwLock::new(user)));

        }

        if let Some((uuid,claims)) = token_to_approve
        {
            cfg.approve_token(uuid,claims);
        }

        for uuid in tokens_uuid_to_revoke
        {
            cfg.revoke_token(&uuid);
        }

        drop(cfg);

        let _ = self._flush_config();

        LoggerMessages::Info(LogInfos::UserReloaded).log();
    }

    pub async fn add_user(
        &self,
        username: String,
        visible_name: Option<String>,
        permissions: Vec<String>,
        quota: Option<String>,
        sudo: bool,
    ) -> Result<(),HTTPMessage>
    {
        let uname=username.trim();

        if self.get_user(uname).await.is_ok()
        {
            return Err(ErrorMessages::E_USER_ALREADY_EXISTS.wrap_with_status_code(Some(vec![Value::String(uname.to_string())])));
        }

        {
            let mut cfg = self.config.lock().await;
            let uid = try_create_unix_user(
                uname,
                self.mountpoint().await,
                sudo,
                cfg.daemon.user_groups.default.clone(),
            ).await.map_err(|e| propagate_error(ErrorMessages::E_NEW_USER, e))?;

            cfg.users.insert(uname.to_string(), CfgUser {
                otp_secret: None,
                uid,
                fullname: visible_name,
                permissions: Some(collapse_permissions(permissions)),
            });
        }

        self.flush_config().await?;

        self.set_user_quota(uname,quota).await?; //this methods also triggers event

        LoggerMessages::Info(LogInfos::UserCreated(uname));

        Ok(())
    }

    pub async fn set_user_quota(&self, uname:&str,quota:Option<String>) -> Result<(),HTTPMessage>
    {
        if let Some((pool,dataset)) = self.get_pool_identifier().await &&
            let Some(q) = quota
            && q.len() > 0
        {
            ZFS(
                ZFSActions::SetQuota(
                    ZFSArgs {pool,dataset:Some(dataset)},
                    ZFSQuotaArgs{username:uname.to_string(),quota: ZFSQuota::Formatted(q)}
                ),false,CmdConfig::default())
                .run()
                .await
                .map_err(|e| propagate_error(ErrorMessages::E_USER_QUOTA,e))?
                .ok_or_else(|| ErrorMessages::E_USER_QUOTA.wrap_with_status_code(None))?
                .is_success()
                .map_err(|e| propagate_error(ErrorMessages::E_USER_QUOTA,e))?;
        }

        let mut ctx:ContextData=HashMap::new();
        ctx.insert(ContextVariables::Account,uname.to_string());

        self.event_manager.trigger(Trigger::Event(Events::UserCreated),Some(ctx)).await;


        Ok(())
    }

    pub async fn get_users(&self) -> Vec<User>
    {
        let users = self.users.lock().await;

        stream::iter(users.iter())
            .then(|u| async  {
                 u.read().await.clone()
            })
            .collect::<Vec<User>>()
            .await
    }

    // Get the list of User structs of admin (ie users with all permissions)
    pub async fn get_admin_users(&self) -> Vec<Arc<RwLock<User>>>
    {
        let users = self.users.lock().await;

        stream::iter(users.iter().cloned())
        .filter_map(
            |user| async move
            {
                let is_admin =
                {
                    let u = user.read().await;
                    u.admin
                };

                if is_admin {Some(user)}
                else {None}
            }
        )
        .collect::<Vec<Arc<RwLock<User>>>>()
        .await

    }

    // Returns a User struct given the username
    pub async fn get_user(&self,username:&str) -> Result<Arc<RwLock<User>>, HTTPMessage>
    {
        let users = self.users.lock().await;

        for user in users.iter()
        {
            let u = user.read().await;
            if u.username == username { return Ok(Arc::clone(&user)); }
        }

        Err(ErrorMessages::E_USER_NOT_FOUND.wrap_with_status_code(Some(vec![Value::String(username.to_string())])))
    }

    pub async fn get_unassociated_sys_users(&self) -> Result<Vec<String>, HTTPMessage>
    {
        let mut system_users: Vec<String> = Vec::new();

        let user_uids = self.get_users()
            .await
            .iter()
            .filter_map(|u| u.uid)
            .collect::<Vec<_>>();

        let output = GetEntPasswd(None,CmdConfig::default()).run()
            .await
            .map_err(|e| propagate_error(ErrorMessages::E_USER_SYSTEM,e))?
            .ok_or( ErrorMessages::E_UNKNOWN.wrap_with_status_code(None))?
            .is_success()
            .map_err(|e| propagate_error(ErrorMessages::E_USER_SYSTEM,e))?;

        for u in output.stdout.lines()
        {
            let tokens = u.split(":").collect::<Vec<&str>>();
            let uid = tokens[2].parse::<u32>().unwrap();

            if (uid>=1000) && (!user_uids.contains(&uid))
            {
                system_users.push(String::from(tokens[0]));
            }
        }

        Ok(system_users)
    }

    pub async fn change_username(&self, old_username:&str, new_username:&str, change_sys_user:bool) -> Result<(), HTTPMessage>
    {
        if old_username != new_username
        {
            let mut cfg = self.config.lock().await;
            if let Some(u) = cfg.users.remove(old_username)
            {
                cfg.users.insert(new_username.to_string(), u);
            } else {
                return Err(ErrorMessages::E_USER_NOT_FOUND.wrap_with_status_code(Some(vec![Value::String(old_username.to_string())])))
            }

            drop(cfg);

            self.flush_config().await?;
        }

        if change_sys_user
        {
            self.change_system_username(old_username, new_username).await?;
        }

        let mut ctx: ContextData = HashMap::new();
        ctx.insert(ContextVariables::Account, old_username.to_string());


        self.event_manager.trigger(
            Trigger::Event(Events::UserModified),
            Some(ctx)
        ).await;


        Ok(())
    }

    async fn change_system_username(&self, old_username:&str, new_username:&str) -> Result<(), HTTPMessage>
    {
        let mut create_new = true;

        let mountpoint = self.mountpoint().await;
        let mut new_homedir = mountpoint.clone();

        if let Some(mut m) = new_homedir
        {
            m.push(new_username);
            new_homedir = Some(m);
        }

        if let Ok(u) = self.get_user(new_username).await
        {
            let user = u.read().await;
            if user.uid.is_some()
            {
                create_new = false;
                let mut cmds = vec![
                    UserMod(UserModAction::ChangeUsername(old_username,new_username),true,CmdConfig::default()),
                    GroupMod(GroupModAction::ChangeName(old_username,new_username),true,CmdConfig::default()),
                ];

                if let Some(new_home) = &new_homedir && let Some(new_path) = new_home.to_str()
                {
                    //the user had a previous home dir => let's rename it
                    if let Some(old_homedir) = &user.home_dir && let Some(old_path) = old_homedir.to_str()
                    {
                        cmds.push(MV(old_path,new_path,CmdConfig::default())); //technically, as the UID hasn't changed, no need to update permissions on FS
                    }
                    else //the user didn't have a home dir - so let's make it
                    {
                        let os_user = OSUser::Name(new_username.to_string());
                        cmds.push(Mkdir(new_path,Some(FileSystemPermissions::from_mode(0o700)),true,CmdConfig::default()));
                        cmds.push(Chown(&os_user, &os_user, &OSUser::Empty, &OSUser::Empty, new_path, false, CmdConfig::default()));
                    }

                    Transaction::new(cmds)
                        .execute()
                        .await
                        .map_err(|e| propagate_error(ErrorMessages::E_USER_SYSTEM,e))?;

                }
            }
        }

        if create_new
        {
            let cfg = self.config.lock().await;

            try_create_unix_user(
                new_username, mountpoint, false,
                cfg.daemon.user_groups.default.clone())
                .await
                .map_err(|e| propagate_error(ErrorMessages::E_USER_SYSTEM,e))?;
        }

        Ok(())
    }



    pub async fn change_fullname(&self, username:&str, fullname:&str) -> Result<(), HTTPMessage>
    {
        let mut cfg = self.config.lock().await;
        if let Some(u) = cfg.users.get_mut(username)
        {
            u.fullname = Some(fullname.to_string());
        }
        else
        {
            return Err(ErrorMessages::E_USER_NOT_FOUND.wrap_with_status_code(Some(vec![Value::String(username.to_string())])))
        }

        drop(cfg);

        self.flush_config().await?;

        let mut ctx: ContextData = HashMap::new();
        ctx.insert(ContextVariables::Account, username.to_string());


        self.event_manager.trigger(
            Trigger::Event(Events::UserModified),
            Some(ctx)
        ).await;


        Ok(())
    }

    pub async fn set_user_permissions(&self, username:&str, permissions:Vec<String>) -> Result<(), HTTPMessage>
    {
        let mut cfg = self.config.lock().await;
        if let Some(u) = cfg.users.get_mut(username)
        {
            u.permissions = Some(collapse_permissions(permissions));
        }
        else
        {
            return Err(ErrorMessages::E_USER_NOT_FOUND.wrap_with_status_code(Some(vec![Value::String(username.to_string())])))
        }

        drop(cfg);

        self.flush_config().await?;

        LoggerMessages::Info(LogInfos::UserChangePermissions(username)).log();

        let mut ctx: ContextData = HashMap::new();
        ctx.insert(ContextVariables::Account, username.to_string());

        self.event_manager.trigger(
            Trigger::Event(Events::UserModified),
            Some(ctx)
        ).await;

        Ok(())
    }

    pub async fn change_uid(&self, username:&str, new_uid:u32) -> Result<(), HTTPMessage>
    {

        let return_err = |info:anyhow::Error| {
            ErrorMessages::E_USER_UID.wrap_with_status_code(Some(
                vec![Value::String(username.to_string()),Value::String(info.to_string())]
            ))
        };

        let current_uid = get_user_uid(username)
            .await
            .map_err(return_err)?;

        let current_gid = get_user_gid(username)
            .await
            .map_err(return_err)?;

        let cmds = vec![
            UserMod(UserModAction::ChangeUID(username,current_uid,new_uid),true,CmdConfig::default()),
            GroupMod(GroupModAction::ChangeGID(username,current_gid,new_uid),true, CmdConfig::default())
        ];

        Transaction::new(cmds)
            .execute()
            .await
            .map_err(|e| return_err(anyhow::Error::new(e)))?;

        restore_user_home_dir(self.mountpoint().await,username)
            .await
            .map_err(return_err)?;


        {
            let mut cfg = self.config.lock().await;
            if let Some(u) = cfg.users.get_mut(username)
            {
                u.uid = new_uid;
            } else {
                return Err(ErrorMessages::E_USER_NOT_FOUND.wrap_with_status_code(Some(vec![Value::String(username.to_string())])));
            }
        }

        self.flush_config().await?;

        let mut ctx: ContextData = HashMap::new();
        ctx.insert(ContextVariables::Account, username.to_string());


        self.event_manager.trigger(
            Trigger::Event(Events::UserModified),
            Some(ctx)
        ).await;

        Ok(())
    }

    pub async fn set_sudo_group(&self, username:&str, sudo:bool) -> Result<(), HTTPMessage>
    {
        let cmd = if sudo { UserMod(UserModAction::SetGroups(username,sudo_group(),true),false,CmdConfig::default()) }
        else { GPasswd(GPasswdAction::RemoveGroup(username,sudo_group()),CmdConfig::default()) };

        cmd.run()
            .await
            .map_err(|e| propagate_error(ErrorMessages::E_USER_SUDO,e))?
            .ok_or_else(|| ErrorMessages::E_USER_SUDO.wrap_with_status_code(None))?
            .is_success()
            .map_err(|e| propagate_error(ErrorMessages::E_USER_SUDO,e))?;

        let mut ctx: ContextData = HashMap::new();
        ctx.insert(ContextVariables::Account, username.to_string());

        LoggerMessages::Warning(LogWarnings::UserSudo(username,sudo)).log();

        self.event_manager.trigger(
            Trigger::Event(Events::UserModified),
            Some(ctx)
        ).await;

        Ok(())
    }

    pub async fn delete_user(&self, username:&str, home_dir_action: HomeDirAction, other_username:Option<&str>) -> Result<(), HTTPMessage>
    {
        {
            let admins = self.get_admin_users().await;

            //self preserving check: avoids that the user deletes the only admin account
            if (admins.len() == 1) && (admins[0].read().await.username == username)
            {
                return Err(ErrorMessages::E_PERM_ADMIN.wrap_with_status_code(None));
            }
        }

        let user_to_delete_lock = self.get_user(username).await?;
        let user_to_delete = user_to_delete_lock.read().await;

        let mut keep_home = false;

        match home_dir_action
        {
            HomeDirAction::Keep => keep_home = true,
            HomeDirAction::Move => {
                if let Some (uname) = other_username
                {
                    let host_user_lock = self.get_user(uname).await?;

                   
                    let host_user = host_user_lock.read().await;

                    let src = user_to_delete.home_dir.as_ref();
                    let dst = host_user.home_dir.as_ref();

                    if let Some(s) = src && let Some(d) = dst
                    {
                        let mut destination = d.clone();
                        destination.push(user_to_delete.username.as_str());

                        if let Some(src_path) = s.to_str() && let Some(dst_path) = destination.to_str()
                        {
                            let chown_user = OSUser::Name(host_user.username.clone());
                            let cmds = vec![
                              Mkdir(dst_path,Some(FileSystemPermissions::from_mode(0o700)),true,CmdConfig::default()),
                              RSync(src_path,dst_path,Some(&["-a"]),CmdConfig::default()),
                              Chown(&chown_user,&chown_user,&chown_user,&chown_user,dst_path,true,CmdConfig::default())
                            ];
                            
                            Transaction::new(cmds)
                                .execute()
                                .await
                                .map_err(|e|
                                    ErrorMessages::E_USER_COPY_FILES.wrap_with_status_code(Some(
                                        vec![
                                            Value::String(user_to_delete.username.to_string()),
                                            Value::String(e.to_string()),
                                        ]
                                    ))
                                )?;
                        }
                    }
                }
                else { keep_home = true } // in case an other user is not specified, let's use the safest option to keep the home dir
            }

            _ => ()
        }
        
        UserDel(user_to_delete.username.as_str(),keep_home,CmdConfig::default())
            .run()
            .await
            .map_err(|e|
                ErrorMessages::E_USER_DELETE.wrap_with_status_code(Some(
                    vec![
                        Value::String(user_to_delete.username.to_string()),
                        Value::String(e.to_string()),
                    ]
                ))
            )?
            .ok_or_else(||
                ErrorMessages::E_USER_DELETE.wrap_with_status_code(Some(
                    vec![
                        Value::String(user_to_delete.username.to_string()),
                        Value::String(String::from("Unable to run userdel")),
                    ]
                ))
            )?
            .is_success()
            .map_err(|e|
                ErrorMessages::E_USER_DELETE.wrap_with_status_code(Some(
                    vec![
                        Value::String(user_to_delete.username.to_string()),
                        Value::String(e.to_string()),
                    ]
                ))
            )?;


        {
            let mut cfg = self.config.lock().await;
            cfg.users.remove(user_to_delete.username.as_str());
        }

        LoggerMessages::Warning(LogWarnings::UserDeleted(user_to_delete.username.as_str())).log();

        drop(user_to_delete);
        
        self.flush_config().await?;

        let mut ctx: ContextData = HashMap::new();
        ctx.insert(ContextVariables::Account, username.to_string());
        
        self.event_manager.trigger(
            Trigger::Event(Events::UserDeleted),
            Some(ctx)
        ).await;

        Ok(())
    }
}


pub async fn get_backend() -> Arc<Backend>
{
    BACKEND.get_or_init( async || {
        let backend = Backend::new().await;
        backend
    }).await.clone()
}
