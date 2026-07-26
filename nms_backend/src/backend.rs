use api::v1::jwt::{create_token,token_verification,TokenPurposes};
use axum::http::StatusCode;
use axum::Json;
use base64::prelude::*;
use chrono::{TimeDelta};
use config::Config;
use crate::backend::api::v1::msg::{StatusMessage, WrappedResponse};
use crate::backend::config::{CfgToken};
use crate::backend::dev::{Device, DiskState};
use crate::backend::jwt::JWTClaim;
use crate::cmdl::{CmdConfig, Executable};
use crate::cmdl::coreutils::Cat;
use crate::cmdl::passwd::{Groups,GetEntPasswd};
use crate::cmdl::zfs::{ZFSActions, ZFSListArgs, ZFSListType, ZPool, ZPoolActions, ZFS};
use crate::events::{ContextData, EventManager, Events, EventParameters};
use crate::thread_wrapper::ThreadWrapper;
use crate::vfs::{Capacity, VFS};
use msg::{ErrorMessages,LoggerMessages,LogWarnings,LogErrors, LogInfos};
use permissions::is_admin;
use regex::RegexBuilder;
use serde_json::Value;
use serde::Serialize;
use std::collections::HashMap;
use std::error::Error;
use std::fs;
use std::io::Read;
use std::net::{SocketAddrV4};
use std::path::Path;
use std::path::PathBuf;
use std::str::FromStr;
use std::sync::{OnceLock,Mutex,Arc, RwLock};
use utils::{get_quota_for_all, sudo_group,ts_to_str,str_to_i64, get_system_disks};
use utils::get_notifications_count;
use uuid::Uuid;

pub type HTTPError = (StatusCode, Json<WrappedResponse>);
pub type FastAPIComp<T> = Result<Json<T>, HTTPError>; //this type is to make it more compatible with the current frontend

pub mod api;
pub mod config;
pub mod dev;
pub mod jwt;
pub mod msg;
pub mod permissions;
pub mod utils;
pub mod net;

static BACKEND:OnceLock<Arc<Backend>> = OnceLock::new();
static NMS_CONFIG_FILE:&str = "nms.conf.json";


pub fn propagate_error<E:Error>(msg:ErrorMessages, err:E) -> HTTPError
{
    msg.wrap_with_status_code(Some(vec![Value::String(err.to_string())]))
}

pub fn propagate_unknown_error<E:Error>(err:E) -> HTTPError
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

#[derive(Debug, Serialize)]
pub struct PoolExtensionStatus
{
    pub is_running:bool,
    pub eta:Option<i64>,
    pub progress:Option<f32>
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

#[derive(Debug, Serialize)]
pub struct Pool
{
    pub name:String,
    pub disks:Vec<Device>,
    pub message:Option<String>,
    pub state:Option<String>,
}


#[derive(Debug, Serialize)]
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

#[derive(Debug, Serialize)]
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



pub struct Backend
{
    config:Mutex<Config>,
    users:Mutex<Vec<Arc<RwLock<User>>>>,
    tmp_secrets:Mutex<HashMap<String,TemporarySecret>>,
    event_manager:Arc<EventManager>,
    secret_key:String,
    mount: RwLock<Option<VFS>>,
    pool_properties: RwLock<Option<PoolProperties>>
}

impl Backend
{
    fn new() -> Arc<Self>
    {
        let backend = Arc::new(Backend{
                config:Mutex::new(Config::default()),
                users:Mutex::new(vec![]),
                tmp_secrets: Mutex::new(HashMap::new()),
                event_manager: EventManager::new(),
                secret_key: "prova".to_string(),
                mount: RwLock::new(None),
                pool_properties:RwLock::new(None)
        });

        if let Err(e) = backend.read_config()
        {
            LoggerMessages::Error(LogErrors::CfgRead(&e.to_string())).log();
            LoggerMessages::Warning(LogWarnings::CfgDefault).log();
            match backend._flush_config()
            {
                Ok(()) => LoggerMessages::Info(LogInfos::NewCfg).log(),
                Err(e) => {
                    LoggerMessages::Error(LogErrors::CfgWrite(&e.to_string())).log();
                    std::process::exit(1)
                }
            }
        }

        LoggerMessages::Info(LogInfos::BackendStarted).log();    



        backend.reload_users();
        let th_backend = Arc::clone(&backend);

        backend.event_manager.register_multiple_events (
            &[&Events::UserCreated,&Events::UserDeleted, &Events::UserModified],
            Arc::new(move |_ctx:&Option<ContextData> | th_backend.reload_users()),
            None
        );

        let th_backend = Arc::clone(&backend);

        backend.event_manager.register_action(
            &Events::Timer,
            Arc::new(
                move |_ctx:&Option<ContextData> |
                {
                    th_backend.update_users();
                }
            ),
            None,
            Some(vec![EventParameters::Timer(3)])
        );

        backend.event_manager.start();

        return backend;
    }

      

    pub fn get_bind_addr(self:&Arc<Self>) -> SocketAddrV4
    {
        let cfg = self.config.lock().unwrap();

        SocketAddrV4::new(
            cfg.daemon.host,
            cfg.daemon.port
        )
    }

    pub fn read_config(self:&Arc<Self>) -> Result<(),Box<dyn Error + '_>>
    {
        let json = fs::read_to_string(NMS_CONFIG_FILE)?;

        let mut cfg = self.config.lock()?;

        *cfg = serde_json::from_str(&json)?;

        cfg.cleanup_tokens();

        Ok(())
    }

    fn _flush_config(self:&Arc<Self>) -> Result<(),std::io::Error>
    {
        let mut tmp_file = NMS_CONFIG_FILE.to_string();
        tmp_file.push('~');

        let result = fs::File::create(&tmp_file);

        if let Err(e) = result
        {
            LoggerMessages::Error(LogErrors::CfgRead(&e.to_string())).log();
            return Err(e.into());
        }
        else 
        {
            let file = result.unwrap();
            let cfg = self.config.lock().unwrap();
            let result = serde_json::to_writer_pretty(file,&(*cfg));

            if let Err(e) = result
            {
                LoggerMessages::Error(LogErrors::CfgWrite(&e.to_string())).log();
                return Err(e.into());
            }

            if let Err(e) = fs::rename(tmp_file, NMS_CONFIG_FILE)
            {
                LoggerMessages::Error(LogErrors::CfgMove(&e.to_string())).log();
                return Err(e.into());
            }

            Ok(())
        }
    }

    pub fn flush_config(self:&Arc<Self>) -> Result<(),HTTPError>
    {
        self._flush_config().map_err(|e| propagate_unknown_error(e))
    }
}

// Auth-related Methods
impl Backend
{
    pub fn verify_token(self:&Arc<Self>, token:&str,requested_purpose:TokenPurposes) -> Result<JWTClaim,HTTPError>
    {
        let claims = token_verification(token, requested_purpose, self.secret_key.as_bytes())?;

        if let Ok(cfg) = self.config.lock()
        {
            if !cfg.is_token_issued(&claims.uuid)
            {
                return Err(ErrorMessages::E_AUTH_REVOKED.wrap_with_status_code(None));
            }
        }

        Ok(claims)
    }

    pub fn push_token(self:&Arc<Self>, token:JWTClaim) -> Result<(),HTTPError>
    {
        match self.config.lock()
        {
            Ok(mut cfg) =>
            {
                cfg.approve_token(token.uuid, token.claims);
                return Ok(());
            }
            Err(e) => 
            {
                LoggerMessages::Error(LogErrors::CfgLock(&e.to_string())).log();
                return Err(ErrorMessages::E_UNKNOWN.wrap_with_status_code(None));
            }
        }
    }

    pub fn revoke_token(self:&Arc<Self>, uuid:&String) -> Result<(),HTTPError>
    {
        match self.config.lock()
        {
            Ok(mut cfg) =>
            {
                cfg.revoke_token(&uuid);
                return Ok(());
            }
            Err(e) => 
            {
                LoggerMessages::Error(LogErrors::CfgLock(&e.to_string())).log();
                return Err(ErrorMessages::E_UNKNOWN.wrap_with_status_code(None));
            }
        }
    }

    pub fn is_otp_configured_for(self:&Arc<Self>,username:&str) -> Result<bool,HTTPError>
    {
        match self.config.lock()
        {
            Ok(cfg) => {
                for (uname,cfg_u) in &cfg.users
                {
                    if uname == username
                    {
                        return Ok(cfg_u.otp_secret.is_some());
                    }
                }

                Err(ErrorMessages::E_USER_NOT_FOUND.wrap_with_status_code(Some(vec![Value::String(username.to_string())])))
            }
            Err(e) => 
            {
                LoggerMessages::Error(LogErrors::CfgLock(&e.to_string())).log();
                Err(ErrorMessages::E_UNKNOWN.wrap_with_status_code(None))
            }
        }
    }

    pub fn is_otp_configured(self:&Arc<Self>) -> bool
    {
        match self.users.lock()
        {
            Err(e) => 
            {
                LoggerMessages::Error(LogErrors::AnyOTPCheck(&e.to_string())).log();
                return true;
            }

            Ok(users) =>
            {
                let mut configured = false;

                match self.config.lock()
                {
                    Ok(cfg) =>
                    {
                        for user in users.iter()
                        {
                            match user.read()
                            {
                                Ok(u) =>
                                {
                                    if u.admin
                                    {
                                        if let Some(u) = cfg.get_user(&u.username)
                                        {
                                            if u.otp_secret.is_some()
                                            {
                                                configured=true;
                                                break;
                                            }
                                        }
                                    }
                                }
                                Err(e) =>
                                {
                                    LoggerMessages::Error(LogErrors::AnyOTPCheck(&e.to_string())).log();
                                    configured = true;
                                }
                            }
                        }
                    }
                    Err(e)  =>
                    {
                        LoggerMessages::Error(LogErrors::AnyOTPCheck(&e.to_string())).log();
                        configured = true;
                    }
                }

                return configured;
            }
        }
    }

    pub fn has_otp_secret(self:&Arc<Self>,username:&String) -> bool
    {
        if let Ok(cfg) = self.config.lock()
        {
            if let Some(user) = cfg.get_user(username)
            {
                return user.otp_secret.is_some();
            }
        }

        return false;
    }

    pub fn add_temporary_secret(self:&Arc<Self>,username:Option<String>,secret:String)
    {
        if let Ok(secrets) = &mut self.tmp_secrets.lock()
        {
            let uuid = Uuid::new_v4();
            secrets.insert(uuid.to_string(),TemporarySecret { uuid: uuid.to_string(), username, secret });
        }
    }

    pub fn get_temporary_secrets(self:&Arc<Self>) -> Result<Vec<TemporarySecret>,HTTPError>
    {
        let secrets = self.tmp_secrets.lock().map_err(|e|
            {
                LoggerMessages::Error(LogErrors::TmpSecretsLock(&e.to_string())).log();
                ErrorMessages::E_UNKNOWN.wrap_with_status_code(None)
            }
        )?;

        Ok(secrets.values().cloned().collect())
    }

    pub fn save_temporary_secret(self:&Arc<Self>,uuid:&String) -> Result<String,HTTPError>
    {
        let is_otp_configured = self.is_otp_configured(); //moved here to avoid deadlocks

        let secrets = &mut self.tmp_secrets.lock().map_err(|e|
            {
                LoggerMessages::Error(LogErrors::TmpSecretsLock(&e.to_string())).log();
                ErrorMessages::E_UNKNOWN.wrap_with_status_code(None)
            })?;

        

        let secret = match secrets.get(uuid)
        {
            Some(s) => s,
            None => {
                LoggerMessages::Warning(LogWarnings::TmpSecretNotFound(uuid)).log();
                return Err(ErrorMessages::E_AUTH_INVALID.wrap_with_status_code(None));
            }
        };


        let cfg = &mut self.config.lock().map_err(|e|{
            LoggerMessages::Error(LogErrors::CfgLock(&e.to_string())).log();
            ErrorMessages::E_UNKNOWN.wrap_with_status_code(None)
        })?;

        
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
                for u in self.get_admin_users()?
                {
                    match u.read()
                    {
                        Ok(usr) => 
                        {
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
                        Err(e) =>
                        {
                            LoggerMessages::Error(LogErrors::UserReadLock(&e.to_string()));
                            return Err(ErrorMessages::E_UNKNOWN.wrap_with_status_code(None))
                        }
                    }
                }
            }

            LoggerMessages::Error(LogErrors::AdminOTPAlreadyConf).log();
            return Err(ErrorMessages::E_AUTH_ALREADY_CONFIG.wrap_with_status_code(None));
        }
    }

    

    pub fn get_otp_secrets(self:&Arc<Self>) -> Result<Vec<(String,String)>,HTTPError>
    {
        match &self.config.lock()
        {
            Ok(cfg) =>
            {
                let mut r:Vec<(String,String)> = Vec::new();

                for (uname,cfg_u) in &cfg.users
                {
                    if let Some(secret) = &cfg_u.otp_secret
                    {
                        r.push((uname.clone(), secret.clone()));
                    }
                }

                return Ok(r);
            }
            Err(e) =>
            {
                LoggerMessages::Error(LogErrors::CfgLock(&e.to_string())).log();
                return Err(ErrorMessages::E_UNKNOWN.wrap_with_status_code(None));
            }
        }
    }

}


// Pool-related Methods
impl Backend
{
    fn get_quota_info(self:&Arc<Self>,log:bool) -> Option<HashMap<String,Quota>>
    {
        if let Ok(cfg) = self.config.lock()
        {
            if let Some(pool) = &cfg.pool
            {
                match get_quota_for_all(&pool.name, &pool.dataset)
                {
                    Ok(map) => {return Some(map);}
                    Err(e) => {
                        if log {LoggerMessages::Warning(LogWarnings::ZfsQuota(&e)).log();}
                        return None;
                    }
                }
            } 
            else
            {
                if log {LoggerMessages::Warning(LogWarnings::ZfsQuotaNoPool).log();}
                return None;
            }
        }

        None
    }

    fn get_pool_identifier(self:&Arc<Self>) -> Option<(String,String)>
    {
        if let Ok(cfg) = self.config.lock()
        {
            if let Some(pool) = &cfg.pool
            {
                return Some((pool.name.clone(),pool.dataset.clone()));
            }
        }

        None
    }

    fn is_mounted(self:&Arc<Self>) -> bool
    {
        if let Ok(l) = self.mount.read()
        {
            return l.is_some();
        }

        false
    }

    fn mountpoint(self:&Arc<Self>) -> Option<PathBuf>
    {
        if self.is_mounted()
        {
            if let Ok(mount) = self.mount.read()
            {
                if let Some(vfs) = &*mount
                {
                    return Some(vfs.basepath());
                }
            }
        }

        None
    }

    fn is_pool_configured(self:&Arc<Self>) -> bool
    {
        self.get_pool_identifier().is_some()
    }

    fn is_pool_present(self:&Arc<Self>) -> bool
    {
        if self.is_pool_configured()
        {
            if let Some(output) = ZPool(
                ZPoolActions::Status(&self.get_pool_identifier().unwrap().0),
                false,None).run()
            {
                return output.is_success().is_ok();
            }
        }

        false
    }

    fn get_pool_status_id(self:&Arc<Self>) -> Option<String>
    {
        if self.is_pool_configured()
        {
            if let Some(output) = ZPool(
                ZPoolActions::Status(&self.get_pool_identifier().unwrap().0),
                false,None
            )
            .run()
            {
                if output.exit_code == 0
                {
                    let status:Value = serde_json::from_str(&output.stdout)
                        .or(serde_json::from_str("{}"))
                        .unwrap();

                    match &status["pools"][self.get_pool_identifier().unwrap().0]["msgid"]
                    {
                        Value::String(id) => return Some(id.to_string()),
                        _ => ()
                    }
                }
            }           
        }

        None
    }

    fn is_any_pool_present(self:&Arc<Self>) -> bool
    {

        if let Some(output) = ZFS(
            ZFSActions::List(
                ZFSListArgs::new(None, Some(ZFSListType::Filesystem), None)
            ), 
            false,None).run()
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

    fn pool_capacity(self:&Arc<Self>) -> Result<Capacity,HTTPError>
    {
        let vfs = self
            .mount
            .read()
            .map_err(|e| ErrorMessages::E_POOL_CAPACITY.wrap_with_status_code(Some(vec![Value::String(e.to_string())])))?;

        match &(*vfs)
        {
            Some(v) => Ok(v.capacity.clone()),
            None => Err(ErrorMessages::E_POOL_MOUNTED.wrap_with_status_code(None))
        }
    }

    fn get_expansion_status(self:&Arc<Self>) -> Result<PoolExtensionStatus,HTTPError>
    {
        if self.is_pool_configured()
        {
            return Err(ErrorMessages::E_POOL_NO_CONF.wrap_with_status_code(None));
        } 

        if !self.has_redundancy()
        {
            return Ok(PoolExtensionStatus::new(false,None,None));
        }

        let pool_name = self.get_pool_identifier().unwrap().0;

        if let Some(output) = ZPool(
            ZPoolActions::Status(&pool_name),
            false,
            None
        ).run()
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

            return Ok(
                    PoolExtensionStatus { is_running: true, eta: None, progress: None }
            );

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

    fn get_importable_pools(self:&Arc<Self>) -> Result<Vec<Pool>,HTTPError>
    {
        let zpool_output = ZPool(
            ZPoolActions::Import(None), 
        false, 
            CmdConfig::default()
        )
        .run()
        .unwrap()
        .is_success()
        .map_err( 
            |e| propagate_unknown_error(e)
        )?;

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
                            )
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


    fn has_redundancy(self:&Arc<Self>)->bool
    {
        if let Ok(r) = self.pool_properties.read()
        {
            !r.is_none() && r.as_ref().unwrap().redundancy
        }
        else {false} 
    }

    fn has_encryption(self:&Arc<Self>)->bool
    {
        if let Ok(r) = self.pool_properties.read()
        {
            !r.is_none() && r.as_ref().unwrap().encryption
        }
        else {false} 
    }

    fn has_compression(self:&Arc<Self>)->bool
    {
        if let Ok(r) = self.pool_properties.read()
        {
            !r.is_none() && r.as_ref().unwrap().compression
        }
        else {false} 
    }

    fn get_key(self:&Arc<Self>)->Result<Option<String>,HTTPError>
    {
        if self.has_encryption()
        {    

            if let Some(cfg_pool) = &self
                .config
                .lock()
                .map_err(|e| propagate_error(ErrorMessages::E_POOL_KEY,e))?
                .pool
            {
                if let Some(key_path) = &cfg_pool.encryption_key
                {
                    let mut cat = Cat(
                        Some(key_path), 
                        Some(&CmdConfig::new(true,true,None,None))
                    )
                    .spawn()
                    .map_err(|e| propagate_error(ErrorMessages::E_POOL_KEY,e))?;

                    let exit_code = cat.wait().map_err(|e| propagate_error(ErrorMessages::E_POOL_KEY,e))?;

                    if !exit_code.success()
                    {
                        return Err(ErrorMessages::E_POOL_KEY.wrap_with_status_code(None));
                    }

                    let mut key_buffer:Vec<u8> = Vec::new();
                    cat.stdout.unwrap().read_to_end(&mut key_buffer).map_err(|e| propagate_error(ErrorMessages::E_POOL_KEY,e))?;

                    return Ok(Some(BASE64_STANDARD.encode(key_buffer)));
                }
            }
        }
        return Ok(None);
    }

    fn get_last_scrub_report(self:&Arc<Self>)->Option<LastScrubReport>
    {        
        if self.is_pool_configured()
        {
            let pool_name = self.get_pool_identifier().unwrap().0;
            let zpool_output = ZPool(
                ZPoolActions::Status(&pool_name), 
                false, 
                CmdConfig::default()
            ).run();

            if let Some(output) = zpool_output
            {
                let m:Value = serde_json::from_str(&output.stdout).or::<Value>(Ok(Value::Null)).unwrap();

                if let Value::Object(scan_stats) = &m["pools"][pool_name]["scan_stats"]
                {
                    if scan_stats["function"].as_str().unwrap() == "SCRUB"
                    {
                        return Some(LastScrubReport::new(
                            str_to_i64(scan_stats["started"].as_str()),
                            str_to_i64(scan_stats["started"].as_str()),
                            scan_stats["errors"].as_str(),
                        ));
                    }
                }
            }


        }

        None
    }

    fn get_current_scrub_info(self:&Arc<Self>)->Option<ScrubLiveInfo>
    {        
        if self.is_pool_configured()
        {
            let pool_name = self.get_pool_identifier().unwrap().0;
            let zpool_output = ZPool(
                ZPoolActions::Status(&pool_name), 
                false, 
                CmdConfig::default()
            ).run();

            if let Some(output) = zpool_output
            {
                let m:Value = serde_json::from_str(&output.stdout).or::<Value>(Ok(Value::Null)).unwrap();

                if let Value::Object(scan_stats) = &m["pools"][pool_name]["scan_stats"]
                {
                    let ongoing: bool = scan_stats["function"].as_str().unwrap() == "SCANNING";
                    let time:Option<i64> = {
                        if let Some(int) = str_to_i64(scan_stats["end_time"].as_str())
                        {
                            if int > 0 { Some(int) }
                            else {None}
                        }
                        else {str_to_i64(scan_stats["start_time"].as_str())}                       
                    };


                    return Some( ScrubLiveInfo::new(ongoing, time));
                }
            }


        }

        None
    }

    fn get_pool_disks(self:&Arc<Self>) -> Vec<Device>
    {
        if self.is_pool_configured()
        {
            if let Ok(guard) = self.pool_properties.read() && let Some(pool_pros) = &(*guard)
            {
                return pool_pros.attached_disks.clone();
            }
        }

        return Vec::new();
    }
}

//Device-related Methods
impl Backend
{
    fn get_disks(self:&Arc<Self>) -> Vec<Device>
    {
        let mut pool_disks = self.get_pool_disks();
        let mut system_disks = get_system_disks();

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


// User-related Methods
impl Backend
{
    fn update_users(self:&Arc<Self>)
    {
        
        if let Some(map) = &mut self.get_quota_info(false)
        {
            if let Ok(users) = self.users.lock()
            {
                for u in users.iter()
                {
                    if let Ok(mut user) = u.write()
                    {
                        user.quota = map.remove(&user.username); 
                        user.notifications = get_notifications_count(&user.username);
                    }                 
                }
            }
        }
    }

    fn reload_users(self:&Arc<Self>)
    {
        if let Ok(mut users) = self.users.lock()
        {
            users.clear();
            let quota_info = self.get_quota_info(true);

            if let Ok(mut cfg) = self.config.lock()
            {

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


                    // sudo detection
                    let cmd_cfg = CmdConfig::new(
                        true,
                        true,
                        None,
                        None
                    );

                    let mut sudo:bool = false;

                    if let Some(group_output) = Groups(&uname,Some(&cmd_cfg)).run()
                    {
                        if group_output.exit_code == 0
                        {
                            if let Some(_) = group_output.stdout.find(sudo_group())
                            {
                                sudo = true;
                            }
                        }
                    }

                    //first token
                    let mut home_dir:Option<String> = None;
                    let mut uid:Option<u32> = None;
                    let mut gid:Option<u32> = None;

                    //get home - uid - gid
                    if let Some(output) = GetEntPasswd(Some(uname.as_str()), Some(&cmd_cfg)).run()
                    {
                        if output.exit_code == 0
                        {
                            let tokens:Vec<&str> = output.stdout.split(":").collect();

                            if tokens.len()>5
                            {
                                uid = Some(tokens[2].parse::<u32>().unwrap());
                                gid = Some(tokens[3].parse::<u32>().unwrap());
                                home_dir = Some(tokens[5].to_string());
                            }
                        }
                    }
                    
                    let user=
                        User{
                            username: uname.to_string(),
                            visible_name: prop.fullname.clone(),
                            permissions: prop.permissions.clone(),
                            quota:quota,
                            sudo:sudo,
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
                            notifications:get_notifications_count(uname)
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
            }
        }

        let _ = self._flush_config();
    }

    pub fn get_admin_users(self:&Arc<Self>) -> Result<Vec<Arc<RwLock<User>>>,HTTPError>
    {
        let users = self.users.lock().map_err(|e|{
            LoggerMessages::Error(LogErrors::AdminUserList(&e.to_string())).log();
            ErrorMessages::E_UNKNOWN.wrap_with_status_code(None)
        })?;

        Ok(
            users
            .iter()
            .filter_map(
                |u|
                {
                    if u.read().map(|x|x.admin).unwrap_or(false)
                    {Some(Arc::clone(u))}
                    else {None}
                }
            )
            .collect()
        )
    }

    pub fn get_user(self:&Arc<Self>,username:&str) -> Result<Arc<RwLock<User>>,HTTPError>
    {
        match &self.users.lock()
        {
            Ok(users) =>
            {
                for user in users.iter()
                {
                    if let Ok(u) = user.read()
                    {    
                        if u.username == username
                        {
                            return Ok(Arc::clone(&user));
                        }
                    }
                }

                Err(ErrorMessages::E_USER_NOT_FOUND.wrap_with_status_code(Some(vec![Value::String(username.to_string())])))
            }
            Err(e) =>
            {
                LoggerMessages::Error(LogErrors::AdminUserList(&e.to_string())).log();
                Err(ErrorMessages::E_UNKNOWN.wrap_with_status_code(None))
            }
        }
    }
}

pub fn get_backend() -> Arc<Backend>
{
    BACKEND.get_or_init(|| {
        Backend::new()
    }).clone()
}

mod test
{
    #[allow(unused)]
    use super::*;

    #[test]
    fn importable_pools_test() -> Result<(), HTTPError>
    {
        let p = get_backend().get_importable_pools()?;

        println!("{:?}",p);

        Ok(())
    }

    #[test]
    fn key_base64_test() -> Result<(), Box<dyn Error>>
    {
        let mut cat = Cat(Some("/root/tank.key"), Some(&CmdConfig::new(true,true,None,None))).spawn()?;

        let exit_code = cat.wait()?;

        if exit_code.code().unwrap() != 0 {panic!("Status code: {}",exit_code)}
        let mut buf:Vec<u8> = Vec::new();
        let stdout = cat.stdout.unwrap().read_to_end(&mut buf);

        println!("{}",BASE64_STANDARD.encode(buf));


        Ok(())
    }
}