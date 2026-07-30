use api::v1::jwt::{create_token,token_verification,TokenPurposes};
use axum::Json;
use axum::http::StatusCode;
use base64::prelude::*;
use chrono::{TimeDelta};
use config::Config;
use crate::backend::api::v1::msg::{StatusMessage, WrappedResponse};
use crate::backend::config::{CfgToken};
use crate::backend::dev::{Device, DiskState};
use crate::backend::jwt::JWTClaim;
use crate::cmdl::coreutils::Cat;
use crate::cmdl::passwd::{Groups,GetEntPasswd};
use crate::cmdl::zfs::{ZFSActions, ZFSListArgs, ZFSListType, ZPool, ZPoolActions, ZFS};
use crate::cmdl::{CmdConfig, Executable};
use crate::events::{ContextData, EventManager, Events, EventParameters};
use crate::task::TaskWrapper;
use crate::vfs::{Capacity, VFS};
use futures::stream::{self, StreamExt};
use msg::{ErrorMessages,LoggerMessages,LogWarnings,LogErrors, LogInfos};
use permissions::is_admin;
use regex::RegexBuilder;
use serde::Serialize;
use serde_json::Value;
use std::collections::HashMap;
use std::error::Error;
use std::net::{SocketAddrV4};
use std::path::Path;
use std::path::PathBuf;
use std::str::FromStr;
use std::sync::Arc;
use std::fmt::{Display, Debug};
use std::marker::Send;
use tokio::sync::{Mutex, RwLock, OnceCell};
use tokio::fs::{File, rename, read_to_string};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use utils::get_notifications_count;
use utils::{get_quota_for_all, sudo_group,ts_to_str,str_to_i64, get_system_disks};
use uuid::Uuid;
use crate::backend::remote_access::init_remote_services;

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
mod remote_access;

static BACKEND:OnceCell<Arc<Backend>> = OnceCell::const_new();
static NMS_CONFIG_FILE:&str = "nms.conf.json";


pub fn propagate_error<E:Display+Debug+Send>(msg:ErrorMessages, err:E) -> HTTPError
{
    msg.wrap_with_status_code(Some(vec![Value::String(err.to_string())]))
}

pub fn propagate_unknown_error<E:Display+Debug+Send>(err:E) -> HTTPError
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
    event_manager:EventManager,
    secret_key:String,
    mount: RwLock<Option<VFS>>,
    pool_properties: RwLock<Option<PoolProperties>>
}

impl Backend
{
    pub async fn new() -> Arc<Self>
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

        {
            let read_cfg_result = backend.read_config().await;

            if let Err(e) = read_cfg_result
            {
                LoggerMessages::Error(LogErrors::CfgRead(&e.to_string())).log();
                LoggerMessages::Warning(LogWarnings::CfgDefault).log();
                let flush_cfg_result = backend._flush_config().await;
                match flush_cfg_result
                {
                    Ok(()) => LoggerMessages::Info(LogInfos::NewCfg).log(),
                    Err(e) => {
                        LoggerMessages::Error(LogErrors::CfgWrite(&e.to_string())).log();
                        std::process::exit(1)
                    }
                }
            }

            LoggerMessages::Info(LogInfos::BackendStarted).log();
        }



        let reload_user_ft = backend.reload_users();

        let task_backend = Arc::clone(&backend);

        backend.event_manager.register_multiple_events (
            &[&Events::UserCreated,&Events::UserDeleted, &Events::UserModified],
            Arc::new(
                Box::new(
                    move |_ctx: &Option<ContextData>|
                    {
                        let b = Arc::clone(&task_backend);
                        Box::pin(
                        async move
                          {
                            b.reload_users().await;
                          })
                        }
                    )
            )
            ,
            None
        ).await;

        let task_backend = Arc::clone(&backend);

        backend.event_manager.register_action(
            &Events::Timer,
            Arc::new(
                Box::new(
                    move |_ctx: &Option<ContextData>|
                        {
                            let b = Arc::clone(&task_backend);
                            Box::pin(
                                async move
                                    {
                                        b.update_users().await;
                                    })
                        }
                )
            ),
            None,
            Some(vec![EventParameters::Timer(3)])
        ).await;

        backend.event_manager.start().await;

        reload_user_ft.await;

        {
            let cfg = backend.config.lock().await;
            init_remote_services(&cfg.access_services).await;
        }


        return backend;
    }

      

    pub async fn get_bind_addr(&self) -> SocketAddrV4
    {
        let cfg = self.config.lock().await;

        SocketAddrV4::new(
            cfg.daemon.host,
            cfg.daemon.port
        )
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

    pub async fn flush_config(&self) -> Result<(),HTTPError>
    {
        self._flush_config().await.map_err(|e| propagate_unknown_error(e))
    }
}

// Auth-related Methods
impl Backend
{
    //verify if a token is valid
    pub async fn verify_token(&self, token:&str,requested_purpose:TokenPurposes) -> Result<JWTClaim,HTTPError>
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

    pub async fn save_temporary_secret(&self,uuid:&String) -> Result<String,HTTPError>
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
        let cfg = self.config.lock().await;

        if let Some(pool) = &cfg.pool
        {
            match get_quota_for_all(&pool.name, &pool.dataset).await
            {
                Ok(map) => {return Some(map);}
                Err(e) => {
                    if log {LoggerMessages::Warning(LogWarnings::ZfsQuota(&e)).log();}
                }
            }
        }
        else
        {
            if log {LoggerMessages::Warning(LogWarnings::ZfsQuotaNoPool).log();}
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
    pub async fn pool_capacity(&self) -> Result<Capacity,HTTPError>
    {
        let vfs = self.mount.read().await;

        match vfs.as_ref()
        {
            Some(v) => Ok(v.capacity.clone()),
            None => Err(ErrorMessages::E_POOL_MOUNTED.wrap_with_status_code(None))
        }
    }

    // Returns the progression status of a pool expansion (ie when a new disk is added to a pool)
    pub async fn get_expansion_status(&self) -> Result<PoolExtensionStatus,HTTPError>
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

    pub async fn get_importable_pools(&self) -> Result<Vec<Pool>,HTTPError>
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
    pub async fn get_key(&self)->Result<Option<String>,HTTPError>
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
        return Ok(None);
    }

    //Returns the last report (if any) of a performed scrub operation on the pool
    pub async fn get_last_scrub_report(&self)->Option<LastScrubReport>
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

    pub async fn get_current_scrub_info(&self)->Option<ScrubLiveInfo>
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
    pub async fn get_user(&self,username:&str) -> Result<Arc<RwLock<User>>,HTTPError>
    {
        let users = self.users.lock().await;

        for user in users.iter()
        {
            let u = user.read().await;
            if u.username == username { return Ok(Arc::clone(&user)); }
        }

        Err(ErrorMessages::E_USER_NOT_FOUND.wrap_with_status_code(Some(vec![Value::String(username.to_string())])))
    }
}

pub async fn get_backend() -> Arc<Backend>
{
    BACKEND.get_or_init( async || {
        let backend = Backend::new().await;
        backend
    }).await.clone()
}

// mod test
// {
//     #[allow(unused)]
//     use super::*;
//
//     #[test]
//     fn importable_pools_test() -> Result<(), HTTPError>
//     {
//         let p = get_backend().get_importable_pools()?;
//
//         println!("{:?}",p);
//
//         Ok(())
//     }
//
//     #[test]
//     fn key_base64_test() -> Result<(), Box<dyn Error>>
//     {
//         let mut cat = Cat(Some("/root/tank.key"), Some(&CmdConfig::new(true,true,None,None))).spawn()?;
//
//         let exit_code = cat.wait()?;
//
//         if exit_code.code().unwrap() != 0 {panic!("Status code: {}",exit_code)}
//         let mut buf:Vec<u8> = Vec::new();
//         let stdout = cat.stdout.unwrap().read_to_end(&mut buf);
//
//         println!("{}",BASE64_STANDARD.encode(buf));
//
//
//         Ok(())
//     }
// }