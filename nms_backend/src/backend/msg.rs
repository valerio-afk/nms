use super::HTTPError;
use axum::{Json, http::StatusCode};
use serde::ser::SerializeStruct;
use serde::{Serialize, Serializer};
use serde_json::Value;
use std::fmt::{Display, Formatter};
use strum::{EnumProperty, IntoStaticStr};
use tracing::{error, info, warn};

pub trait StatusMessage:Clone
{
    fn wrap(self:&Self,params:Option<Vec<Value>>) -> WrappedResponse;
    fn wrap_with_status_code(self:&Self,params:Option<Vec<Value>>) -> HTTPError;
}


#[derive(Debug,  IntoStaticStr)]
pub enum MessageTypes
{
    // #[serde(rename="error")]
    Error(ErrorMessages),

    // #[serde(rename="warning")]
    Warning,

    // #[serde(rename="success")]
    Success(SuccessMessages)
}

impl Serialize for MessageTypes
{
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        // 3 is the number of fields in the struct.
        let mut state = serializer.serialize_struct("MessageType", 2)?;

        match self
        {
            MessageTypes::Error(err) => {
                state.serialize_field("type","error")?;
                let code: &'static str = err.into();
                state.serialize_field("code",code)?;
            }
            MessageTypes::Warning => {
                state.serialize_field("type","warning")?;
                // let code: &'static str = err.into();
                // state.serialize_field("code",code)?;
            }
            MessageTypes::Success(msg) => {
                state.serialize_field("type","success")?;
                let code: &'static str = msg.into();
                state.serialize_field("code",code)?;
            }
        }

        state.end()
    }
}

#[derive(Debug, Serialize)]
pub struct MessageResponse
{
    #[serde(flatten)]
    code:MessageTypes,
    params:Option<Vec<Value>>
}

impl Display for MessageTypes
{
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result
    {
        write!(f, "{:?}", self)
    }
}

#[derive(Debug, Serialize)]
pub struct WrappedResponse
{
    detail:MessageResponse
}

impl Display for WrappedResponse
{
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result
    {
        write!(f, "{:?}", self)
    }
}

impl WrappedResponse
{
    pub fn to_json(self) -> Json<WrappedResponse>
    {
        Json(self)
    }
}

#[derive(Debug, Serialize, Clone, EnumProperty, IntoStaticStr)]
pub enum ErrorMessages
{
    E_UNKNOWN,
    E_UNKNOWN_RESPONSE,
    E_PROPERTY,
    E_CSRF,
    E_UNKNOWN_METHOD,
    E_READ_FILE,
    E_SELINUX_PORT,
    E_SYSTEMD_START,
    E_SYSTEMD_STOP,
    E_TOO_MANY_REQ,
    E_INVALID_VALUE,
    
    #[strum(props(status_code="401"))]
    E_NO_PERM,

    E_POOL_ALREADY_CONF,
    E_POOL_NO_CONF,
    E_POOL_CONFIG,
    E_POOL_DISK_UNAVAL,
    E_POOL_NEW,
    E_POOL_DESTROY,
    E_POOL_REDUNDANCY_MIN,
    E_POOL_EXPAND,
    E_POOL_EXPAND_INFO,
    E_POOL_EXPAND_STATUS,
    E_POOL_KEY,
    E_POOL_KEY_IMPORT,
    E_POOL_LIST,
    E_POOL_RECOVERY,
    E_POOL_DISKS,
    E_POOL_DISK_REPLACE,
    E_POOL_ATTACH,
    E_POOL_DETACH,
    E_POOL_MOUNT,
    E_POOL_UNMOUNT,
    E_POOL_MOUNTED,
    E_POOL_UNMOUNTED,
    E_POOL_SCRUB,
    E_POOL_RM_MOUNTPOINT,
    E_POOL_INVALID_MOUNTPOINT,
    E_POOL_MOUNT_STATUS,
    E_POOL_MOUNTPOINT,
    E_POOL_FORMAT,
    E_POOL_CAPACITY,
    E_POOL_OPENED,
    E_POOL_DISK_MISSING,
    E_POOL_CORRUPTED,
    E_POOL_OUTDATED,
    E_POOL_SNAPSHOT_NAME,
    E_POOL_SNAPSHOT_CREATE,
    E_POOL_SNAPSHOT_DELETE,
    E_POOL_SNAPSHOTS,
    E_POOL_SNAPSHOT_ROLLBACK,

    #[strum(props(status_code="403"))]
    E_AUTH_ALREADY_CONFIG,
    
    #[strum(props(status_code="401"))]
    E_AUTH_INVALID,

    #[strum(props(status_code="401"))]
    E_AUTH_EXPIRED,

    #[strum(props(status_code="401"))]
    E_AUTH_REVOKED,
    
    #[strum(props(status_code="400"))]
    E_AUTH_MALFORMED,

    #[strum(props(status_code="401"))]
    E_AUTH_NOT_CONF,

    #[strum(props(status_code="403"))]
    E_AUTH_WRONG_OTP,

    E_DISK_ATTACH,
    E_DISK_FORMAT,
    E_DISK_SELF_TEST,

    E_FS_CH_PERM,

    E_APT_GET,
    E_APT_UNK,

    E_ACCESS_ENABLED,
    E_ACCESS_DISABLED,
    E_ACCESS_DISABLING,
    E_ACCESS_SERV_UNK,
    E_ACCESS_PROP,

    E_NET_CHANGE_STATE,
    E_NET_CONNECTION_STATUS,
    E_NET_INVALID_NETMASK,
    E_NET_INVALID_IP_ADDRESS,
    E_NET_INVALID_GATEWAY,
    E_NET_INVALID_DNS,
    E_NET_WIFI_LIST,
    E_NET_WIFI_CONNECT,
    E_NET_WIFI_DEV,
    E_NET_AP,
    E_NET_VPN_NOTCONF,
    E_NET_VPN_STATE,
    E_NET_VPN_KEY,
    E_NET_VPN_GEN_PRIVATE,
    E_NET_VPN_GEN_PUBLIC,
    E_NET_VPN_CONF,
    E_NET_VPN_USER,
    E_NET_VPN_USER_INVALID,
    E_NET_VPN_IP_MAX,
    E_NET_DDNS_INVALID,
    E_NET_DDNS_SERVICE,
    E_NET_DDNS_CONFIG,

    #[strum(props(status_code="404"))]
    E_USER_NOT_FOUND,

    E_USER_PASSWD,
    E_USER_QUOTA,
    E_USER_NAME,
    E_USER_SUDO,
    E_NEW_USER,
    E_PERM_ADMIN,
    E_DEL_ADMIN,
    E_USER_COPY_FILES,
    E_USER_DELETE,
    E_USER_LOGIN_RESET,
    E_USER_SYSTEM,
    E_USER_UID,

    E_SYSTEM_UPDATES,
    E_SYSTEM_DIST,

    E_FS_NOT_FILE,
    E_FS_ZIP,
    E_FS_UNZIP,
    E_REL_PATH,
    E_FS_COPY,
    E_FS_MOVE,
    E_FS_MKDIR,

    E_EVENT_INVALID,
    E_ACTION_INVALID,
    E_EVENT_INVALID_ACTION,
    E_EVENT_INVALID_PARAM
}

impl StatusMessage for ErrorMessages
{
    fn wrap(&self,params:Option<Vec<Value>>) -> WrappedResponse
    {
        WrappedResponse { 
            detail: MessageResponse 
            { 
                code: MessageTypes::Error(self.clone()),
                params:params
            }
        }    
    }
    fn wrap_with_status_code(&self,params:Option<Vec<Value>>) -> HTTPError
    {
        let status_code_str:&'static str = {
            match self.get_str("status_code")
            {
                Some(value) => value,
                None => "500"
            }
        };

        let status_code:u16 = match status_code_str.parse::<u16>() {
            Ok(code) => code,
            Err(_) => 500
        };

        (
            match StatusCode::from_u16(status_code)
            {
                Ok(status) => status,
                Err(_) => StatusCode::INTERNAL_SERVER_ERROR,
            },
            self.wrap(params).to_json()
        )
    }
}

#[derive(Debug, Serialize, Clone, EnumProperty, IntoStaticStr)]
pub enum SuccessMessages
{
    S_POOL_CREATED,
    S_POOL_EXPANDED,
    S_POOL_FORMATTED,
    S_POOL_DESTROYED,
    S_POOL_MOUNTED,
    S_POOL_UNMOUNTED,
    S_POOL_SCRUB,
    S_POOL_SNAPSHOT_CREATE,
    S_POOL_SNAPSHOT_DELETE,
    S_POOL_SNAPSHOT_ROLLBACK,

    S_APT_UPDATE,
    S_APT_UPGRADE,
    
    S_OTP_DANGEROUS,
    
    S_RECOVERY,
    
    S_ACCESS_ENABLED,
    S_ACCESS_UPDATED,
    S_ACCESS_DISABLED,
    
    S_DISK_FORMATTED,
    S_DISK_SELF_TEST,
    
    S_POOL_REPLACE_DISK,
    
    S_NET_VPN_KEYSGEN,
    S_NET_VPN_CONFIG,
    S_NET_CONFIG,
    S_NET_VPN_PEER_DELETED,
    S_NET_VPN_PEER_ADDED,
    S_NET_DDNS_ENABLED,
    S_NET_DDNS_DISABLED,
    S_NET_AP,
    
    S_USER_PASSWORD,
    S_USER_FULLNAME,
    S_USER_QUOTA,
    S_USER_NAME,
    S_USER_SUDO,
    S_NEW_USER,
    S_USER_PERM,
    S_DEL_USER,
    S_USER_LOGIN_RESET,
    S_USER_UID,
    
    S_EVENT_ADDED,
    S_EVENT_ENABLED,
    S_EVENT_DISABLED,
    S_EVENT_DELETED,
    S_EVENT_UPDATED
}

impl StatusMessage for SuccessMessages
{
    fn wrap(&self,params:Option<Vec<Value>>) -> WrappedResponse
    {
        WrappedResponse {
            detail: MessageResponse
            {
                code: MessageTypes::Success(self.clone()),
                params:params
            }
        }
    }
    fn wrap_with_status_code(&self,params:Option<Vec<Value>>) -> HTTPError
    {
        (
            StatusCode::OK,
            self.wrap(params).to_json()
        )
    }
}




pub enum LogErrors<'a>
{
    ServerCannotStart(&'a String),
    FirstLoginToken(&'a str,&'a String),
    LoginToken(&'a Option<String>,&'a String),
    AnyOTPCheck(&'a String),
    TokenRevoked(&'a str),
    CfgLock(&'a String),
    CfgRead(&'a String),
    CfgWrite(&'a String),
    CfgMove(&'a String),
    TmpSecretsLock(&'a String),
    AdminOTPAlreadyConf,
    OTPAlreadyConf(&'a Option<String>),
    AdminUserList(&'a String),
    SecretEncoding(&'a String),
    NewTOTPURI(&'a String),
    TmpOTPVerification(&'a String),
    OTPInit(&'a Option<String>,&'a String,),
    OTPWrong,
    UserReadLock(&'a String),
    UnexpectedJWT(&'a String),
    VFSInit(&'a String),
    PoolConfig(&'a String),
    Automount(&'a String),
    SnapshotInit(&'a String),
}

impl<'a> Display for LogErrors<'a>
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {

        match self
        {
            LogErrors::ServerCannotStart(e) => write!(f,"Unable to serve backend: {}",e),
            LogErrors::FirstLoginToken(uname, e) => write!(f,"Error while generating first login token for {}: {}",uname,e),
            LogErrors::LoginToken(uname, e) => match uname
            {
                Some(u) => write!(f,"Error while generating login token for {}: {}",u,e),
                None => write!(f,"Error while generating login token: {}",e),
            }
            LogErrors::AnyOTPCheck(e) => write!(f,"Unable to determine if any OTP is configured (return true for safety reasons): {}", e),
            LogErrors::TokenRevoked(uuid) => write!(f,"An attempt to login with a revoken token has been made: {}",uuid),
            LogErrors::CfgLock(e) => write!(f,"Unable to access configuration file: {}",e),
            LogErrors::CfgRead(e) => write!(f,"Unable to read configuration file: {}",e),
            LogErrors::CfgWrite(e) => write!(f,"Unable to write configuration file: {}",e),
            LogErrors::CfgMove(e) => write!(f,"Unable to move configuration file: {}",e),
            LogErrors::TmpSecretsLock(e) => write!(f,"Unable to get temporary secrets: {}",e),
            LogErrors::AdminOTPAlreadyConf => write!(f,"Attempting to reset already configured secret for an admin user"),
            LogErrors::OTPAlreadyConf(username) => match username
            {
                Some(u) =>  write!(f,"Attempting to reset already configured secret for {}",u),
                None =>  write!(f,"Attempting to reset already configured secret for a user"),
            }            
            LogErrors::AdminUserList(e) => write!(f,"Unable to retrieve the list of admin users: {}",e),
            LogErrors::UserReadLock(e) => write!(f,"Unable to get read lock for: {}",e),
            LogErrors::SecretEncoding(e) => write!(f,"Unable to encode secret key: {}",e),
            LogErrors::NewTOTPURI(e) => write!(f,"Unable to generate new TOTP provisioning URL: {}",e),
            LogErrors::TmpOTPVerification(e) => write!(f,"Unable to verifiy temporary OTP: {}",e),
            LogErrors::OTPInit(uname, e) => match uname
            {
                Some(u) =>  write!(f,"Unable to initialise OTP verification for {}: {}",u, e),
                None =>  write!(f,"Unable to initialise OTP verification: {}", e)

            }
            LogErrors::OTPWrong => write!(f,"Login attempt failed"),
            LogErrors::UnexpectedJWT(e) => write!(f,"Unexpected JWT: {}",e),
            LogErrors::VFSInit(e) => write!(f,"VFS init failed: {}",e),
            LogErrors::PoolConfig(e) => write!(f,"Pool configuration failed: {}",e),
            LogErrors::Automount(e) => write!(f,"Automount failed: {}",e),
            LogErrors::SnapshotInit(e) => write!(f,"Pool snapshot init failed: {}",e),

        }
    }
}


pub enum LogWarnings<'a>
{
    CfgDefault,
    ZfsQuota(&'a str),
    ZfsQuotaNoPool,

    TmpSecretNotFound(&'a str),
    EMStopped,
    
    PoolUnmountedBy(&'a str),

    RemoteServiceStopped(&'a str, Option<&'a str>),
}

impl<'a> Display for LogWarnings<'a>
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {

        match self
        {
            LogWarnings::CfgDefault => write!(f,"Creating a new configuration file with default values"),
            LogWarnings::ZfsQuota(msg) => write!(f,"Unable to retrieve ZFS quota information: {}",msg),
            LogWarnings::ZfsQuotaNoPool => write!(f,"Unable to obtain quota information as pool is not configured"),
            LogWarnings::TmpSecretNotFound(uuid) => write!(f,"Temporary secret {} not found",uuid),
            LogWarnings::EMStopped => write!(f,"Event Manager stopped"),
            LogWarnings::PoolUnmountedBy(uname) => write!(f,"Pool unmounted by {}",uname),
            LogWarnings::RemoteServiceStopped(srv, usr) => {
                match usr
                {
                    Some(u) => write!(f,"Remote service {} stopped by {}",srv,u),
                    None => write!(f,"Remote service {} stopped",srv)
                }
            }
        }
    }
}


pub enum LogInfos<'a>
{
    NewCfg,
    BackendStarted,
    OTPSecretConf(&'a String),
    OTPSecretGen(&'a Option<String>),
    EMStarted,
    PoolMountedBy(&'a str),
    
}

impl<'a> Display for LogInfos<'a>
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {

        match self
        {
            LogInfos::NewCfg => write!(f,"New configuration file created"),
            LogInfos::BackendStarted => write!(f,"NMS backend started"),
            LogInfos::OTPSecretConf(uname) => write!(f,"OTP secret configured successfully for {}",uname),
            LogInfos::OTPSecretGen(username) => match username
            {
                Some(u) =>  write!(f,"New OTP secret successfully generated for {}",u),
                None =>  write!(f,"New OTP secret successfully generated"),
            },
            LogInfos::EMStarted => write!(f,"Event Manager started"),
            LogInfos::PoolMountedBy(uname) => write!(f,"Pool mounted by {}",uname)
        }
    }
}

pub enum LoggerMessages<'a>
{
    Error(LogErrors<'a>),
    Warning(LogWarnings<'a>),
    Info(LogInfos<'a>),
}

impl<'a> LoggerMessages<'a>
{
    pub fn log(&self)
    {
        match self
        {
            LoggerMessages::Error(e) => error!("{}",e.to_string()),
            LoggerMessages::Warning(w) => warn!("{}",w.to_string()),
            LoggerMessages::Info(info) => info!("{}",info.to_string()),
        }
    }
}
