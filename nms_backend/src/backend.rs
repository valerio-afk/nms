use config::Config;
use utils::{get_quota_for_all, sudo_group};
use std::path::{Path,PathBuf};
use std::fs;
use std::net::SocketAddrV4;
use std::error::Error;
use std::sync::{OnceLock,Mutex,Arc};
use std::collections::HashMap;
use tracing::{info,error,warn};

use permissions::is_admin;
use jwt::{create_token,Token,TokenPurposes};
use utils::get_notifications_count;
use crate::backend::config::CfgToken;
use crate::cmdl::{CmdConfig, Executable};
use crate::cmdl::passwd::{Groups,GetEntPasswd};
use crate::events::{ContextData, EventManager, Events};


pub mod config;
pub mod api;
pub mod utils;
pub mod permissions;
pub mod jwt;

static BACKEND:OnceLock<Arc<Backend>> = OnceLock::new();
static NMS_CONFIG_FILE:&str = "nms.conf.json";

#[derive(Clone)]
pub struct Quota
{
    pub quota:Option<u64>,
    pub used: Option<u64>
}

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
    users:Mutex<Vec<User>>,
    event_manager:Arc<EventManager>,
    secret_key:String
}

impl Backend
{
    fn new() -> Arc<Self>
    {
        let backend = Arc::new(Backend{
                config:Mutex::new(Config::default()),
                users:Mutex::new(vec![]),
                event_manager: EventManager::new(),
                secret_key: "prova".to_string()
        });

        backend.read_config();        
        backend.reload_users();
        let th_backend = Arc::clone(&backend);

        backend.event_manager.register_multiple_events (
            &[&Events::UserCreated,&Events::UserDeleted, &Events::UserModified],
            Arc::new(move |_ctx:&Option<ContextData> | th_backend.reload_users()),
            None
        );

        return backend;
    }

    fn reload_users(self:&Arc<Self>)
    {
        if let Ok(mut users) = self.users.lock()
        {
            users.clear();

            if let Ok(mut cfg) = self.config.lock()
            {
                let quota_info:Option<HashMap<String,Quota>> = {
                    if let Some(pool) = &cfg.pool
                    {
                        match get_quota_for_all(&pool.name, &pool.dataset)
                        {
                            Ok(map) => Some(map),
                            Err(e) => {
                                error!("Unable to read quota information: {e}");
                                None
                            }
                        }
                    } 
                    else
                    {
                        warn!("Unable to obtain quota information as pool is not configured");
                        None
                    }
                };

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
                    
                    users.push(
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
                                    let previous_issued_tokens = cfg.find_tokens_by_purpose(jwt::TokenPurposes::FirstLogin, Some(uname));

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
                                                error!("Error while generating first login token for {uname}: {e}");
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
                                            b.expire_date.cmp(&a.expire_date)
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
                        }
                    )
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


    pub fn is_otp_configured(self:&Arc<Self>) -> bool
    {
        //TODO: fix this
        false
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

        Ok(())
    }

    pub fn flush_config(self:&Arc<Self>) -> Result<(),Box<dyn Error + '_>>
    {
        let mut tmp_file = NMS_CONFIG_FILE.to_string();
        tmp_file.push('~');

        let result = fs::File::create(&tmp_file);

        if let Err(e) = result
        {
            error!("Unable to open configuration file: {e}");
            return Err(Box::new(e));
        }
        else 
        {
            let file = result.unwrap();
            let cfg = self.config.lock().unwrap();
            let result = serde_json::to_writer_pretty(file,&(*cfg));

            if let Err(e) = result
            {
                error!("Unable to save configuration file: {e}");
                return Err(Box::new(e));
            }

            match fs::rename(tmp_file, NMS_CONFIG_FILE)
            {
                Err(e) => {
                    error!("Unable to move configuration file: {e}");
                    return Err(Box::new(e));
                },
                _ => ()
            }

            Ok(())
        }
    }
}

pub fn get_backend() -> Arc<Backend>
{
    BACKEND.get_or_init(|| {
        //read configuration file
        let backend = Backend::new();

        {

            info!("NMS Backend started");

            if let Err(err) = backend.read_config()
            {
                error!("Unable to read configuration file:{err}");
                warn!("Creating a new configuration file with default values");
                match backend.flush_config()
                {
                    Ok(()) => info!("New configuration file created"),
                    Err(_) => std::process::exit(1)
                }
            }

            info!("NMS Backend initialised");        
        }

        backend
    }).clone()
}