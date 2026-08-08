use std::collections::hash_set::Intersection;
use std::collections::HashSet;
use crate::backend::{propagate_unknown_error, Backend, FastAPIComp, HTTPMessage, BackgroundTaskInformation};
use crate::backend::api::BackendPropertyResponse;
use crate::backend::permissions::{UserPermissions, check_permission};
use crate::backend::jwt::TokenPurposes;
use super::disks::CompatibleDisk;
use std::sync::Arc;
use axum::{Json, Router};
use axum::routing::{get, post};
use axum::extract::{State,Path};
use axum_auth::AuthBearer;
use serde_json::Value;
use serde::{Deserialize, Serialize};
use crate::backend::msg::{ErrorMessages, LogInfos, LogWarnings, LoggerMessages, StatusMessage, SuccessMessages};
use crate::dev::{get_system_disks, DiskState, Device};

#[derive(Debug,Serialize)]
struct PoolFlags
{
    encryption:bool,
    redundancy:bool,
    compression:bool
}

impl PoolFlags
{
    pub async fn from_backend(backend:Arc<Backend>) -> PoolFlags
    {
        PoolFlags{
            encryption : backend.has_encryption().await,
            redundancy : backend.has_redundancy().await,
            compression : backend.has_compression().await,
        }
    }
}

#[derive(Clone,Debug,Deserialize, Serialize)]
enum PoolProperties
{
    #[serde(rename = "pool_name")]
    PoolName,

    #[serde(rename = "dataset_name")]
    DatasetName,

    #[serde(rename = "mountpoint")]
    Mountpoint,

    #[serde(rename = "is_mounted")]
    IsMounted,

    #[serde(rename = "is_configured")]
    IsConfigured,

    #[serde(rename = "is_present")]
    IsPresent,

    #[serde(rename = "any_pool_present")]
    AnyPoolPresent,

    #[serde(rename = "pool_capacity")]
    PoolCapacity,

    #[serde(rename = "expansion_status")]
    ExpansionStatus,

    #[serde(rename = "pool_list")]
    PoolList,

    #[serde(rename = "encryption_key")]
    EncryptionKey,

    #[serde(rename = "status_id")]
    StatusId,

    #[serde(rename = "pool_settings")]
    PoolSettings,

    #[serde(rename = "last_scrub_report")]
    LastScrubReport,

    #[serde(rename = "scrub_info")]
    ScrubInfo,

    #[serde(rename = "disks")]
    PoolDisks,

    #[serde(rename = "attachable-disks")]
    AttachableDisks,
    
    #[serde(rename = "snapshot")]
    Snapshots
}

#[derive(Debug,Deserialize)]
struct ImportPool
{
    pool_name:String,
    load_key: bool
}

async fn get_attachable_disks(backend:Arc<Backend>) -> Vec<Device>
{
    let config_disks = backend.get_pool_disks().await;
    let sys_disks = get_system_disks().await;
    let sys_disks = sys_disks.iter().filter(|d| d.state == DiskState::NEW);
    let mut physical_paths:Vec<String> = Vec::new();
    let mut attachable_disks:Vec<Device> = Vec::new();

    for dev in config_disks
    {
        physical_paths.extend(dev.paths.iter().map(|p| p.to_string()));
    }

    let phys_paths_set:HashSet<String> = HashSet::from_iter(physical_paths.into_iter());

    for dev in sys_disks
    {
        let dev_paths_set: HashSet<String> = dev.paths.iter().map(|p| p.clone()).collect();
        let intersection:Intersection<String,_> = phys_paths_set.intersection(&dev_paths_set);
        if intersection.count() == 0
        {
            attachable_disks.push(dev.clone());
        }
    }

    attachable_disks
}


async fn get_pool_property(
    Path(property):Path<PoolProperties>,
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<BackendPropertyResponse<PoolProperties>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::PoolConfGetInfo).await?;

    Ok(Json(BackendPropertyResponse {
        property: property.clone(),
        value: match property
        {
            PoolProperties::PoolName => if let Some(p) = backend.get_pool_identifier().await {Value::String(p.0)} else {Value::Null},
            PoolProperties::DatasetName => if let Some(p) = backend.get_pool_identifier().await {Value::String(p.1)} else {Value::Null},
            PoolProperties::IsMounted => Value::Bool(backend.is_mounted().await),
            PoolProperties::Mountpoint => 
            {
                let mnt = backend.mountpoint().await;
                if let Some(p) = mnt
                {
                    if let Some(s) = p.to_str() { Value::String(s.to_string()) }
                    else {Value::Null}
                }
                else { Value::Null }
            }
            PoolProperties::IsConfigured => Value::Bool(backend.is_pool_configured().await),
            PoolProperties::PoolCapacity => serde_json::to_value(
                backend.pool_capacity().await?
            ).map_err(|e| propagate_unknown_error(e))?,
            PoolProperties::IsPresent => Value::Bool(backend.is_pool_present().await),
            PoolProperties::AnyPoolPresent => Value::Bool(backend.is_any_pool_present().await),
            PoolProperties::ExpansionStatus => serde_json::to_value(
                backend.get_expansion_status().await?
            ).map_err(|e| propagate_unknown_error(e))?,
            PoolProperties::PoolList => serde_json::to_value(backend.get_importable_pools().await?).map_err(|e| propagate_unknown_error(e))?,
            PoolProperties::EncryptionKey => {
                let key = backend.get_key().await?;
                match key
                {
                    Some(key) => Value::String(key),
                    None => Value::Null
                }
            }
            PoolProperties::StatusId => {
                let status_id = backend.get_pool_status_id().await;
                match status_id
                {
                    Some(id) => Value::String(id),
                    None => Value::Null
                }
            }
            PoolProperties::LastScrubReport => {
                let last_report = backend.get_last_scrub_report().await;
                match last_report
                {
                    Some(report) => serde_json::to_value(report).map_err(|e| propagate_unknown_error(e))?,
                    None => Value::Null
                }
            }
            PoolProperties::ScrubInfo => {
                let scrub_info = backend.get_current_scrub_info().await;
                match scrub_info
                {
                    Some(info) => serde_json::to_value(info).map_err(|e| propagate_unknown_error(e))?,
                    None => Value::Null
                }
            }
            PoolProperties::PoolSettings => serde_json::to_value(
                PoolFlags::from_backend(backend).await
            ).map_err(|e| propagate_unknown_error(e))?,
            PoolProperties::PoolDisks => serde_json::to_value(
                backend.get_pool_disks().await.iter().map(|d| CompatibleDisk::from_device(d)).collect::<Vec<CompatibleDisk>>()
            ).map_err(|e| propagate_unknown_error(e))?,
            PoolProperties::AttachableDisks => serde_json::to_value(
                get_attachable_disks(backend).await.iter().map(|d| CompatibleDisk::from_device(d)).collect::<Vec<CompatibleDisk>>()
            ).map_err(|e| propagate_unknown_error(e))?,
            PoolProperties::Snapshots => serde_json::to_value(
                backend.get_pool_snapshots().await
            ).map_err(|e| propagate_unknown_error(e))?,
        }
    }))
}

async fn pool_unmount(AuthBearer(token): AuthBearer, State(backend): State<Arc<Backend>>) -> Result<HTTPMessage,HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::PoolToolsMount).await?;

    let u = user.read().await;

    backend.unmount(Some(&*u)).await?;

    LoggerMessages::Warning(LogWarnings::PoolUnmountedBy(&u.username)).log();

    Ok(SuccessMessages::S_POOL_UNMOUNTED.wrap_with_status_code(None))
}

async fn pool_mount(AuthBearer(token): AuthBearer, State(backend): State<Arc<Backend>>) -> Result<HTTPMessage,HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::PoolToolsMount).await?;

    let u = user.read().await;

    backend.mount(Some(&*u)).await?;

    LoggerMessages::Info(LogInfos::PoolMountedBy(&u.username)).log();

    Ok(SuccessMessages::S_POOL_MOUNTED.wrap_with_status_code(None))
}

async fn pool_detatch(AuthBearer(token): AuthBearer, State(backend): State<Arc<Backend>>) -> FastAPIComp<()>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::PoolConfImport).await?;

    let u = user.read().await;

    backend.export_pool(Some(&*u)).await?;

    LoggerMessages::Warning(LogWarnings::PoolExport(Some(u.username.as_str()))).log();

    Ok(Json(()))
}

async fn pool_attach(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>,
    Json(data): Json<ImportPool>,
) -> FastAPIComp<()>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::PoolConfImport).await?;

    let u = user.read().await;

    backend.import_pool(
        data.pool_name.as_str(),
        data.load_key,
        Some(&*u)
    ).await?;

    LoggerMessages::Info(LogInfos::PoolImport(&data.pool_name, Some(u.username.as_str()))).log();

    Ok(Json(()))
}

async fn start_scrub(AuthBearer(token): AuthBearer, State(backend): State<Arc<Backend>>) -> FastAPIComp<BackgroundTaskInformation>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::PoolToolsVerify).await?;

    let id =backend.start_scrub().await?;
    let task = backend.get_task_by_id(&id.to_string()).await;

    if let Some(task) = task { Ok(Json(task)) }
    else { Err(ErrorMessages::E_POOL_SCRUB.wrap_with_status_code(None)) }
}


pub fn get_route() -> Router<Arc<Backend>>
{
   
    Router::new().nest("/pool",
        Router::new()
            .route("/get/{property}", get(get_pool_property))
            .route("/mount", post(pool_mount))
            .route("/unmount", post(pool_unmount))
            .route("/detach", post(pool_detatch))
            .route("/attach", post(pool_attach))
            .route("/scrub", post(start_scrub))
    )
}

