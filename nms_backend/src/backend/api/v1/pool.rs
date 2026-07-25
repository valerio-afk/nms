use crate::backend::{Backend, FastAPIComp, propagate_unknown_error};
use crate::backend::api::BackendPropertyResponse;
use crate::backend::permissions::{UserPermissions, check_permission};
use crate::backend::jwt::TokenPurposes;
use std::sync::Arc;
use axum::{Json, Router};
use axum::routing::get;
use axum::extract::{State,Path};
use axum_auth::AuthBearer;
use serde_json::Value;
use serde::{Deserialize, Serialize};

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
    ScrubInfo
}

async fn get_pool_property(
    Path(property):Path<PoolProperties>,
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<BackendPropertyResponse<PoolProperties>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login)?;
    let user = backend.get_user(&jwt.claims.username.unwrap())?;

    check_permission(&user, UserPermissions::PoolConfGetInfo)?;

    Ok(Json(BackendPropertyResponse {
        property: property.clone(),
        value: match property
        {
            PoolProperties::PoolName => if let Some(p) = backend.get_pool_identifier() {Value::String(p.0)} else {Value::Null},
            PoolProperties::DatasetName => if let Some(p) = backend.get_pool_identifier() {Value::String(p.1)} else {Value::Null},
            PoolProperties::IsMounted => Value::Bool(backend.is_mounted()),
            PoolProperties::Mountpoint => 
            {
                if let Some(p) = backend.mountpoint() 
                {
                    if let Some(s) = p.to_str() { Value::String(s.to_string()) }
                    else {Value::Null}
                }
                else { Value::Null }
            }
            PoolProperties::IsConfigured => Value::Bool(backend.is_pool_configured()),
            PoolProperties::PoolCapacity => serde_json::to_value(backend.pool_capacity()?).map_err(|e| propagate_unknown_error(e))?,
            PoolProperties::IsPresent => Value::Bool(backend.is_pool_present()),
            PoolProperties::AnyPoolPresent => Value::Bool(backend.is_any_pool_present()),
            PoolProperties::ExpansionStatus => serde_json::to_value(backend.get_expansion_status()?).map_err(|e| propagate_unknown_error(e))?,
            PoolProperties::PoolList => serde_json::to_value(backend.get_importable_pools()?).map_err(|e| propagate_unknown_error(e))?,
            PoolProperties::EncryptionKey => match backend.get_key()?
            {
                Some(key) => Value::String(key),
                None => Value::Null
            }
            _ => Value::Null
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

