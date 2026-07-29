use crate::backend::{Backend, FastAPIComp, propagate_unknown_error};
use crate::backend::api::BackendPropertyResponse;
use crate::backend::permissions::{UserPermissions, check_permission};
use crate::backend::jwt::TokenPurposes;
use super::disks::CompatibleDisk;
use std::sync::Arc;
use axum::{Json, Router};
use axum::routing::get;
use axum::extract::{State,Path};
use axum_auth::AuthBearer;
use serde_json::Value;
use serde::{Deserialize, Serialize};

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
    PoolDisks
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
        }
    }))
}

pub fn get_route() -> Router<Arc<Backend>>
{
   
    Router::new().nest("/pool",
        Router::new()
        .route("/get/{property}", get(get_pool_property))
    )
}

