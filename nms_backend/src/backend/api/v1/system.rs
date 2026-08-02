use axum_auth::AuthBearer;
use axum::Json;
use axum::routing::{Router, get, post};
use axum::extract::{Path, State};
use crate::backend::{Backend, FastAPIComp, BACKEND_VERSION, HTTPError, propagate_unknown_error};
use crate::backend::jwt::TokenPurposes;
use crate::backend::permissions::{UserPermissions, check_permission};
use std::sync::Arc;
use std::time::UNIX_EPOCH;
use sysinfo::{System, MINIMUM_CPU_UPDATE_INTERVAL};
use serde_json::Value;
use indexmap::IndexMap;
use psutil::host::{boot_time};
use serde::{Deserialize, Serialize};
use tracing::warn;
use crate::backend::api::BackendPropertyResponse;
use crate::cmdl::acpi::{Reboot, Shutdown};
use crate::cmdl::{CmdConfig, CommandLine, Executable};
use crate::events::{ContextData, ContextVariables, EventData, Events, Trigger};

#[derive(Clone,Debug,Deserialize, Serialize)]
enum SystemProperties
{
    #[serde(rename = "system_information")]
    SysInfo,
}

async fn get_system_information(backend: Arc<Backend>) -> IndexMap<&'static str, Value>
{
    let mut sys_info: IndexMap<&'static str, Value> = IndexMap::new();

    if let Ok(bt) = boot_time() && let Ok(secs) = bt.duration_since(UNIX_EPOCH)
    {
        sys_info.insert("uptime", Value::from(secs.as_secs()));
    }
    sys_info.insert("nms_ver", Value::from(BACKEND_VERSION));

    let mut sys = System::new_all();

    tokio::time::sleep(MINIMUM_CPU_UPDATE_INTERVAL).await;

    let cpus = sys.cpus();

    if cpus.len() > 0
    {
        let cpu = &cpus[0];
        sys_info.insert("cpu", Value::from(format!("{} with {} core(s)", cpu.vendor_id(), cpus.len())));
    }

    sys_info.insert("os", Value::from(System::long_os_version()));
    sys_info.insert("cpu_load", Value::from(sys.global_cpu_usage().round() as u32));

    sys_info.insert("memory_load", Value::from(((sys.used_memory() as f32)/(sys.total_memory() as f32) * 100.0).round() as u32));
    sys_info.insert("swap_load", Value::from(((sys.used_swap() as f32)/(sys.total_swap() as f32) * 100.0).round() as u32));




    sys_info.insert("net_counters", serde_json::to_value(&backend.get_net_counter().await).unwrap());

    return sys_info;
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
                    Value::from_iter(get_system_information(backend).await)
                },
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


async fn acpi_exec(token:String, backend: Arc<Backend>, cmd:CommandLine,event:Events) -> Result<(), HTTPError>
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
) -> Result<(),HTTPError>
{
    acpi_exec(token,backend,Shutdown(CmdConfig::default()),Events::SystemPoweroff).await
}

async fn reboot(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> Result<(),HTTPError>
{
    acpi_exec(token,backend,Reboot(CmdConfig::default()),Events::SystemReboot).await
}


pub fn get_route() -> Router<Arc<Backend>>
{
    Router::new().nest("/system",
        Router::new()
        .route("/shutdown", post(shutdown))
        .route("/restart", post(reboot))
        .route("/test", get(test))
        .route("/get/{prop}", get(get_sys_property))
    )
}