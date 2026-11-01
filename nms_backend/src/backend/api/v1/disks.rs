use crate::backend::api::BackendPropertyResponse;
use crate::backend::jwt::TokenPurposes;
use crate::backend::permissions::{UserPermissions, check_permission};
use crate::dev::{format_disk, get_system_disks};
use crate::backend::{propagate_unknown_error, Backend, FastAPIComp, HTTPMessage};
use crate::dev::{Device, DiskState};
use axum::extract::{Path, Query, State};
use axum::routing::{get, post};
use axum::{Json, Router};
use axum_auth::AuthBearer;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use axum::http::HeaderMap;
use serde_json::Value;
use crate::backend::msg::{StatusMessage, SuccessMessages};

#[derive(Clone,Debug,Deserialize, Serialize)]
enum DisksProperties
{
    #[serde(rename = "disks")]
    Disks,

    #[serde(rename = "sys-disks")]
    SystemDisks,
}


//this struct is used to return a json compatible with the current API
#[derive(Debug,Serialize)]
pub struct CompatibleDisk
{
    name:String,
    model: String,
    serial: String,
    size:Option<u64>,
    status:DiskState,
    path:String
}

impl CompatibleDisk
{
    pub fn from_device(dev:&Device) -> CompatibleDisk
    {
        CompatibleDisk 
        { 
            name: dev.name.clone(),
            model: dev.model.clone().unwrap_or("".to_string()),
            serial: dev.serial_number.clone().unwrap_or("".to_string()),
            size: Some(dev.size),
            status: dev.state.clone(),
            path: {
                if dev.paths.len()>0 { dev.paths[0].clone() }
                else { format!("/dev/{}",dev.name) }
            } 
        }
    }
}

#[derive(Debug,Deserialize)]
pub struct DiskFormat
{
    dev:String
}

async fn get_disks_property(
    Path(property):Path<DisksProperties>,
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<BackendPropertyResponse<DisksProperties>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::ClientDashboardDisks).await?;

    Ok(Json(BackendPropertyResponse {
        property: property.clone(),
        value: serde_json::to_value(match property
            {
                DisksProperties::Disks =>
                    {
                        let devs = backend.get_disks().await;
                        devs
                    },
                DisksProperties::SystemDisks => get_system_disks().await
                
            }
            .iter()
            .map(|d| CompatibleDisk::from_device(d)).collect::<Vec<CompatibleDisk>>()
        ).map_err(|e| propagate_unknown_error(e))?,
    }))
}

async fn disk_format(
    Query(params):Query<DiskFormat>, //to fix
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>,
    headers: HeaderMap
) -> Result<HTTPMessage,HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    backend.verify_extra_auth_from_headers(headers,TokenPurposes::FormatDisk).await?;

    check_permission(&user, UserPermissions::PoolDisksFormat).await?;

    format_disk(params.dev.as_str()).await?;

    Ok(SuccessMessages::S_DISK_FORMATTED.wrap_with_status_code(Some(vec![Value::String(params.dev.to_string())])))
}

pub fn get_route() -> Router<Arc<Backend>>
{
   
    Router::new().nest("/disks",
        Router::new()
        .route("/get/{property}", get(get_disks_property))
        .route("/format", post(disk_format))
    )
}

