use chrono::Utc;
use crate::events::Events;
use crate::events::actions::UserDefinedActions;
use serde::{Deserialize,Serialize};
use std::collections::HashMap;
use std::net::Ipv4Addr;
use strum::Display;
use super::api::v1::jwt::TokenPurposes;
use super::utils::{DistroFamily, detect_distro_family};


#[derive(Debug, Deserialize, Serialize)]
pub struct CfgPool
{
    pub name: String,
    pub dataset: String,
    pub encryption_key: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CfgDockerService
{
    pub image_name:String,
    pub container_name: String,
    pub port: u32,
    pub user:Option<String>
}
#[derive(Debug, Deserialize, Serialize)]
pub struct CfgSystemdService
{
    units: Vec<String>
}

impl CfgSystemdService
{
    pub fn get_units(&self) -> Vec<String>
    {
        self.units.iter().cloned().collect()
    }
}

#[derive(Debug, Deserialize, Serialize)]
pub enum AccessService
{
    Systemd(CfgSystemdService),
    Docker(CfgDockerService)
}

#[derive(Debug, Deserialize, Serialize,Clone)]
pub struct CfgUser
{
    #[serde(default)]
    pub otp_secret: Option<String>,

    pub uid: u32,
    
    #[serde(default)]
    pub fullname:Option<String>,
    
    #[serde(default)]
    pub permissions: Option<Vec<String>>

}

#[derive(Debug, Deserialize, Serialize)]
pub struct CfgVPN
{
    pub port: u32,

    #[serde(default)]
    pub peers: Option<Vec<String>>,

    #[serde(default)]
    pub endpoint: Option<Ipv4Addr>
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CfgAP
{
    ssid:String,
    psk:String,
    iface:String
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CfgNetworking
{
    #[serde(default="init_vpn")]
    pub vpn:CfgVPN,
    
    #[serde(default)]
    pub ap:Option<CfgAP>
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct CfgDynDNS
{
    #[serde(default)]
    pub enabled:bool,
    pub protocol:String,
    #[serde(default)]
    pub server: Option<String>,
    #[serde(default)]
    pub username: Option<String>,
    #[serde(default)]
    pub password: Option<String>,
    #[serde(default)]
    pub hostname: Option<String>
}


#[derive(Debug, Deserialize, Serialize)]
pub struct CfgAPTUpdates
{
    #[serde(default)]
    last_check:Option<u64>,

    #[serde(default)]
    packages: Option<Vec<String>>
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CfgUpdates
{
    apt:CfgAPTUpdates,
    
    #[serde(default)]
    releases:Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CfgSharedWith
{
    #[serde(default)]
    can_edit:bool
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CfgShares
{
    #[serde(default)]
    expare_date:Option<u64>,

    #[serde(default)]
    shared_with: Option<HashMap<String,CfgSharedWith>>
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CfgActionParameters
{
    action_parameters: HashMap<String,String>,

    #[serde(default)]
    event_parameters: Option<HashMap<String,String>>
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CfgUserDefinedEvents
{
    event: Events,
    action: UserDefinedActions,
    enabled: bool,
    parameters: CfgActionParameters
}



#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct CfgToken
{
    pub purpose: TokenPurposes,
    pub username: Option<String>,
    pub exp: i64
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CfgDaemonUserGroups
{
    pub default:Vec<String>,
    pub smb:String
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CfgDaemon
{
    pub host:Ipv4Addr,
    pub port:u16,
    pub mbox_basepath:String,
    pub user_groups: CfgDaemonUserGroups,
    pub ddns_refresh_time:u8
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Config
{
    #[serde(default="init_daemon")]
    pub daemon: CfgDaemon,

    #[serde(default)]
    pub pool:Option<CfgPool>,

    #[serde(default="init_users")]
    pub users:HashMap<String,CfgUser>,

    #[serde(default = "init_access_services")]
    pub access_services:HashMap<String,AccessService>,

    #[serde(default)]
    pub ddns:Option<HashMap<String,CfgDynDNS>>,
    
    pub networking:CfgNetworking,

    pub updates: CfgUpdates,

    #[serde(default = "init_systemd_services")]
    pub systemd: Vec<String>,

    #[serde(default)]
    pub shares: Option<CfgShares>,

    pub events:Option<HashMap<String,CfgUserDefinedEvents>>,

    pub released_tokens:Option<HashMap<String,CfgToken>>,

}

#[derive(Debug, Display)]
pub enum CfgError
{
    DDNSNotFound,
    DDnsNotConfigured
}





impl Default for Config
{
    fn default() -> Self 
    {
        Config { 
            daemon: init_daemon(),
            pool: None, 
            users: init_users(), 
            access_services: init_access_services(), 
            ddns: None, 
            networking: CfgNetworking { 
                vpn: init_vpn(), 
                ap: None,
            },
            updates: CfgUpdates { 
                apt: CfgAPTUpdates { last_check: None, packages: None }, 
                releases: None,
            }, 
            systemd: init_systemd_services(), 
            shares: None, 
            events: None, 
            released_tokens: None 
        }    
    }
}

impl Config
{
    pub fn cleanup_tokens(&mut self)
    {
        if let Some(map) = &mut self.released_tokens
        {
            let now = Utc::now().timestamp();
            map.retain(|_,v| v.exp>=now );
        }
    }

    pub fn find_tokens_by_purpose(&self, purpose: TokenPurposes,username:Option<&String>) -> HashMap<String, CfgToken>
    {
        if let Some(map) = &self.released_tokens
        {
            map
            .iter()
            .filter(|&(_,value)| value.purpose == purpose )
            .filter(|&(_, value)| {
                match username {
                    Some(u) => {
                        if let Some(uname) = &value.username { uname == u }
                        else { false }
                    }
                    None => true,
                }
            })
            .map(|(k,v)| (k.clone(),v.clone()) )
            .collect()
        }
        else {HashMap::new()}
    }

    pub fn approve_token(&mut self, uuid:String,token:CfgToken)
    {
        self.cleanup_tokens();

        if self.released_tokens.is_none()
        {
            self.released_tokens = Some(HashMap::new());
        }

        self.released_tokens.as_mut().unwrap().insert(uuid,token);
        
    }

    pub fn revoke_token(&mut self, uuid:&String)
    {
        self.cleanup_tokens();

        if let Some(m) = &mut self.released_tokens
        {
            let _ = m.remove(uuid);
        }
    }

    pub fn get_token(&self,uuid:&String) -> Option<CfgToken>
    {
        match &self.released_tokens
        {
            Some(m) => m.get(uuid).cloned(),
            None=> None
        }        
    }

    pub fn is_token_issued(&self,uuid:&String) -> bool
    {
        self.get_token(uuid).is_some()
    }

    pub fn get_user(&self,username:&String) -> Option<CfgUser>
    {
        self.users.get(username).cloned()
    }
    

}


fn init_access_services() -> HashMap<String,AccessService>
{
    let mut map: HashMap<String,AccessService> = HashMap::new();

    let distro_family = detect_distro_family();
    
    let ssh_suffix = match distro_family
    {
        DistroFamily::Rh => "d",
        _ => ""
    };

    let smb_suffix = match distro_family
    {
        DistroFamily::Deb => "d",
        _ => ""
    };

    map.insert("ssh".to_string(), 
                AccessService::Systemd(
                        CfgSystemdService { 
                            units: vec![format!("ssh{ssh_suffix}.service")]
                        }
    ));

    map.insert("ftp".to_string(), 
                AccessService::Systemd(
                        CfgSystemdService { 
                            units: vec!["vsftpd.service".to_string()]
                        }
    ));

    map.insert("nfs".to_string(), 
                AccessService::Systemd(
                        CfgSystemdService { 
                            units: vec![
                                "rpcbind.service".to_string(),
                                "nfs-server.service".to_string(),
                            ]
                        }
    ));

    map.insert("smb".to_string(), 
                AccessService::Systemd(
                        CfgSystemdService { 
                            units: vec![
                                format!("smb{smb_suffix}.service"),
                                format!("nmb{smb_suffix}.service"),
                            ]
                        }
    ));

    map.insert("web".to_string(), 
                AccessService::Systemd(
                        CfgSystemdService { 
                            units: vec!["nginx.service".to_string()]
                        }
    ));

    map.insert("mediaserver".to_string(), 
                AccessService::Docker(
                    CfgDockerService 
                    { 
                        image_name: "jellyfin/jellyfin".to_string(),
                        container_name: "jellyfin_server".to_string(),
                        port: 9000, 
                        user: None 
                    }
                )
    );

    return map;    
}

fn init_systemd_services() -> Vec<String>
{
    vec![
        "nginx.service".to_string(),
        "nmswebapp.service".to_string(),
        "nmsbackend.service".to_string(),
        "wg-quick@wg0.service".to_string(),
        "ddclient.service".to_string()
    ]
}

fn init_daemon () -> CfgDaemon
{
    CfgDaemon {
        host: Ipv4Addr::new(127, 0, 0, 1),
        port: 8081,
        mbox_basepath: String::from("/var/mail"),
        user_groups: CfgDaemonUserGroups {
            default: vec!["plugdev","netdev","users"].iter().map(|x|x.to_string()).collect(),
            smb: "sambashare".to_string(),
        },
        ddns_refresh_time: 10
    }
}

fn init_users() -> HashMap<String,CfgUser>
{
    let mut map:HashMap<String,CfgUser> = HashMap::new();

    map.insert("user".to_string(), CfgUser { 
        otp_secret: None, 
        uid: 1000, fullname: 
        Some("admin".to_string()), 
        permissions: Some(vec!["*".to_string()]),
    });

    map
}

fn init_vpn() -> CfgVPN
{
    CfgVPN
    {
        port: 51820,
        peers: None,
        endpoint: None
    }
}