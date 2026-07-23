use api::v1::jwt::{create_token,token_verification,TokenPurposes};
use axum::http::StatusCode;
use axum::Json;
use config::Config;
use serde::Serialize;
use std::path::Path;
use crate::backend::api::v1::msg::{StatusMessage, WrappedResponse};
use crate::backend::config::{CfgToken};
use crate::backend::jwt::JWTClaim;
use crate::cmdl::{CmdConfig, Executable};
use crate::cmdl::passwd::{Groups,GetEntPasswd};
use crate::events::{ContextData, EventManager, Events, EventParameters};
use crate::thread_wrapper::ThreadWrapper;
use crate::vfs::VFS;
use msg::{ErrorMessages,LoggerMessages,LogWarnings,LogErrors, LogInfos};
use permissions::is_admin;
use serde_json::Value;
use std::collections::HashMap;
use std::error::Error;
use std::fs;
use std::net::SocketAddrV4;
use std::path::PathBuf;
use std::sync::{OnceLock,Mutex,Arc, RwLock};
use utils::{get_quota_for_all, sudo_group};
use utils::get_notifications_count;
use uuid::Uuid;

pub type HTTPError = (StatusCode, Json<WrappedResponse>);
pub type FastAPIComp<T> = Result<Json<T>, HTTPError>; //this type is to make it more compatible with the current frontend

pub mod config;
pub mod api;
pub mod utils;
pub mod permissions;
pub mod msg;
pub mod jwt;

static BACKEND:OnceLock<Arc<Backend>> = OnceLock::new();
static NMS_CONFIG_FILE:&str = "nms.conf.json";

#[derive(Clone,Debug, Serialize)]
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

pub struct Backend
{
    config:Mutex<Config>,
    users:Mutex<Vec<Arc<RwLock<User>>>>,
    tmp_secrets:Mutex<HashMap<String,TemporarySecret>>,
    event_manager:Arc<EventManager>,
    secret_key:String,
    mount: RwLock<Option<VFS>>,
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
                mount: RwLock::new(None)
        });

        backend.read_config();        
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

    pub fn flush_config(self:&Arc<Self>) -> Result<(),Box<dyn Error + '_>>
    {
        let mut tmp_file = NMS_CONFIG_FILE.to_string();
        tmp_file.push('~');

        let result = fs::File::create(&tmp_file);

        if let Err(e) = result
        {
            LoggerMessages::Error(LogErrors::CfgRead(&e.to_string())).log();
            return Err(Box::new(e));
        }
        else 
        {
            let file = result.unwrap();
            let cfg = self.config.lock().unwrap();
            let result = serde_json::to_writer_pretty(file,&(*cfg));

            if let Err(e) = result
            {
                LoggerMessages::Error(LogErrors::CfgWrite(&e.to_string())).log();
                return Err(Box::new(e));
            }

            match fs::rename(tmp_file, NMS_CONFIG_FILE)
            {
                Err(e) => {
                    LoggerMessages::Error(LogErrors::CfgMove(&e.to_string())).log();
                    return Err(Box::new(e));
                },
                _ => ()
            }

            Ok(())
        }
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
                        if group_output.status_code == 0
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
                        if output.status_code == 0
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

        self.flush_config();
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
        //read configuration file
        let backend = Backend::new();
        {

            if let Err(e) = backend.read_config()
            {
                LoggerMessages::Error(LogErrors::CfgRead(&e.to_string())).log();
                LoggerMessages::Warning(LogWarnings::CfgDefault).log();
                match backend.flush_config()
                {
                    Ok(()) => LoggerMessages::Info(LogInfos::NewCfg).log(),
                    Err(_) => std::process::exit(1)
                }
            }

            LoggerMessages::Info(LogInfos::BackendStarted).log();
        }

        backend
    }).clone()
}