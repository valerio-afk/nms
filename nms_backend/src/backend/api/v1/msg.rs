use axum::Json;
use serde::{Serialize,Deserialize};
use serde_json::Value;

pub trait StatusMessage:Clone
{
    fn wrap(self:&Self,params:Option<Vec<Value>>) -> WrappedResponse;
}


#[derive(Debug, Serialize)]
#[serde(tag = "type")]
pub enum MessageTypes
{
    #[serde(rename="error")]
    Error(ErrorMessages),

    #[serde(rename="warning")]
    Warning,

    #[serde(rename="success")]
    Success
}

#[derive(Debug, Serialize)]
pub struct MessageResponse
{
    #[serde(flatten)]
    code:MessageTypes,
    params:Option<Vec<Value>>
}

#[derive(Debug, Serialize)]
pub struct WrappedResponse
{
    detail:MessageResponse
}

impl WrappedResponse
{
    pub fn to_json(self) -> Json<WrappedResponse>
    {
        Json(self)
    }
}

#[derive(Debug, Serialize, Clone)]
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
    E_AUTH_ALREADY_CONFIG,
    E_AUTH_INVALID,
    E_AUTH_EXPIRED,
    E_AUTH_REVOKED,
    E_AUTH_MALFORMED,
    E_AUTH_NOT_CONF,
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
    fn wrap(self:&Self,params:Option<Vec<Value>>) -> WrappedResponse
    {
        WrappedResponse { 
            detail: MessageResponse 
            { 
                code: MessageTypes::Error(self.clone()),
                params:params
            }
        }    
    }
}

