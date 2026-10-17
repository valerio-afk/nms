use axum_auth::AuthBearer;
use axum::Json;
use axum::routing::{Router, get, post};
use axum::extract::{Path, State};
use crate::backend::{Backend, FastAPIComp, HTTPMessage, propagate_unknown_error, BackgroundTaskInformation};
use crate::backend::jwt::TokenPurposes;
use crate::backend::permissions::{UserPermissions, check_permission};
use std::sync::Arc;
use serde_json::Value;
use serde::{Deserialize, Serialize};
use tracing::warn;
use crate::backend::api::BackendPropertyResponse;
use crate::backend::config::CfgNMSRelease;
use crate::backend::msg::{StatusMessage, SuccessMessages};
use crate::cmdl::acpi::{Reboot, Shutdown};
use crate::cmdl::{CmdConfig, CommandLine, Executable};
use crate::events::{ContextData, ContextVariables, Events, Trigger};
use crate::sensors::{get_sensors, Sensor};

#[derive(Clone,Debug,Deserialize, Serialize)]
enum SystemProperties
{
    #[serde(rename = "system_information")]
    SysInfo,

    #[serde(rename = "last_apt_time")]
    LastUpdate,

    #[serde(rename = "system_updates")]
    Packages
}

async fn get_sys_property(
    Path(property):Path<SystemProperties>,
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<BackendPropertyResponse<SystemProperties>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::ClientDashboardAdvanced).await?;

    Ok(Json(BackendPropertyResponse {
        property: property.clone(),
        value: match property
        {
            SystemProperties::SysInfo =>
                {
                    Value::from_iter(backend.get_system_information().await)
                },
            SystemProperties::LastUpdate =>
                {
                    Value::from(backend.get_last_apt_update_time().await)
                }
            SystemProperties::Packages =>
                {
                    if let Some(pkg) = backend.get_upgradeable_packages().await
                    {
                        Value::from_iter(pkg)
                    }
                    else
                    {
                        Value::Null
                    }
                }
        }
    }))
}


    async fn test(AuthBearer(token): AuthBearer, State(backend):State<Arc<Backend>>) -> FastAPIComp<()>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::ClientDashboardAccess).await?;

    Ok(Json(()))
}


async fn acpi_exec(token:String, backend: Arc<Backend>, cmd:CommandLine,event:Events) -> Result<(), HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::ClientDashboardAdvanced).await?;
    let uname = user.read().await.username.clone();

    let mut ctx = ContextData::new();

    match event
    {
        Events::SystemPoweroff => warn!("System shutdown requested by {}. Bye!",uname),
        Events::SystemReboot => warn!("System reboot requested by {}. Bye!",uname),
        _ => ()
    }

    ctx.insert(ContextVariables::TriggerUser, uname);

    backend.event_manager.trigger(Trigger::Event(event),Some(ctx.clone())).await;
    backend.event_manager.trigger(Trigger::Event(Events::SystemShutdown),Some(ctx)).await;
    
    cmd.run().await.map_err(|e| propagate_unknown_error(e))?;
    Ok(())
}

async fn shutdown(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> Result<(), HTTPMessage>
{
    acpi_exec(token,backend,Shutdown(CmdConfig::default()),Events::SystemPoweroff).await
}

async fn reboot(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> Result<(), HTTPMessage>
{
    acpi_exec(token,backend,Reboot(CmdConfig::default()),Events::SystemReboot).await
}


async fn system_sensors(AuthBearer(token): AuthBearer, State(backend): State<Arc<Backend>>) -> FastAPIComp<Vec<Sensor>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::ClientDashboardAdvanced).await?;

    Ok(Json(get_sensors().await))
}

async fn get_task_info(
    Path(task_id): Path<String>,
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<Option<BackgroundTaskInformation>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::ClientDashboardAdvanced).await?;

    Ok(Json(backend.get_task_by_id(&task_id).await))

}

async fn get_nms_cached_release(AuthBearer(token): AuthBearer, State(backend): State<Arc<Backend>>) -> FastAPIComp<Option<CfgNMSRelease>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::ClientDashboardAdvanced).await?;

    Ok(Json(backend.get_nms_release().await))
}

async fn restart_services(AuthBearer(token): AuthBearer, State(backend): State<Arc<Backend>>) -> Result<HTTPMessage,HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::SysAdminSystemctl).await?;

    backend.restart_systemd_services().await?;

    Ok(SuccessMessages::S_SYSTEMD_RESTART.wrap_with_status_code(None))
}

pub fn get_route() -> Router<Arc<Backend>>
{
    Router::new().nest("/system",
        Router::new()
        .route("/shutdown", post(shutdown))
        .route("/restart", post(reboot))
        .route("/test", get(test))
        .route("/sensors", get(system_sensors))
        .route("/get/{prop}", get(get_sys_property))
        .route("/task/{task_id}", get(get_task_info))
        .route("/nms/updates",get(get_nms_cached_release))
        .route("/restart-systemd-services",post(restart_services))
    )
}