use axum_auth::AuthBearer;
use axum::Json;
use axum::routing::{Router, get};
use axum::extract::{Path, State};
use crate::backend::{Backend, FastAPIComp, BACKEND_VERSION};
use crate::backend::jwt::TokenPurposes;
use crate::backend::permissions::{UserPermissions, check_permission};
use std::sync::Arc;
use sysinfo::{System,   MINIMUM_CPU_UPDATE_INTERVAL};
use serde_json::Value;
use indexmap::IndexMap;
use psutil::host::{uptime};
use serde::{Deserialize, Serialize};
use crate::backend::api::BackendPropertyResponse;

#[derive(Clone,Debug,Deserialize, Serialize)]
enum SystemProperties
{
    #[serde(rename = "system_information")]
    SysInfo,
}

async fn get_system_information(backend: Arc<Backend>) -> IndexMap<&'static str, Value>
{
    let mut sys_info: IndexMap<&'static str, Value> = IndexMap::new();

    if let Ok(uptime) = uptime()
    {
        sys_info.insert("uptime", Value::from(uptime.as_secs()));
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


pub fn get_route() -> Router<Arc<Backend>>
{
    Router::new().nest("/system",
        Router::new()
        .route("/test", get(test))
        .route("/get/{prop}", get(get_sys_property))
    )
}