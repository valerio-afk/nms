use axum::extract::{State, Path};
use axum::routing::{get, post};
use axum::{Router, Json};
use axum_auth::AuthBearer;
use crate::backend::jwt::TokenPurposes;
use crate::backend::msg::{ErrorMessages, StatusMessage, SuccessMessages};
use crate::backend::permissions::{check_permission, UserPermissions};
use crate::backend::remote_access::{get_remote_services, ServiceProperty, AbstractRemoteService};
use crate::backend::{propagate_error, Backend, FastAPIComp, propagate_unknown_error, HTTPMessage};
use indexmap::IndexMap;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::str::FromStr;
use std::sync::Arc;


#[derive(Serialize, Debug)]
struct RemoteService
{
    name:String,
    properties: HashMap<ServiceProperty, Value>,
    active:bool
}

#[derive(Deserialize, Debug)]
#[serde(rename_all = "lowercase")]
enum ServiceAction
{
    Enable,
    Disable,
    Update,
}

async fn service_manage(
    service: &AbstractRemoteService,
    action: ServiceAction,
) -> Result<(),HTTPMessage>
{

    let service_name = service.read().await.service_name().await.to_string();

    let mut s = service.write().await;

    let (method,err) =   match action
    {
        ServiceAction::Enable => (s.start(), ErrorMessages::E_ACCESS_ENABLED),
        ServiceAction::Disable => (s.stop(), ErrorMessages::E_ACCESS_DISABLED),
        ServiceAction::Update => (s.restart(), ErrorMessages::E_ACCESS_ENABLED)
    };



    method
        .await
        .map_err(move |e| err.wrap_with_status_code(Some(
            vec![
                Value::from_str(&service_name).unwrap(),
                Value::from_str(e.to_string().as_str()).unwrap()

            ]
        )))?;

    Ok(())
}

async fn list_access_services(AuthBearer(token): AuthBearer, State(backend):State<Arc<Backend>>) -> FastAPIComp<IndexMap<String,RemoteService>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::ClientDashboardAccess).await?;

    let remote_srv = get_remote_services()
        .await
        .map_err(|e| propagate_unknown_error(e))?;

    let mut srvc:IndexMap<String,RemoteService> = IndexMap::new();

    for service in remote_srv.iter()
    {
        let mut properties:HashMap<ServiceProperty,Value> = HashMap::new();
        let mut s = service.write().await;

        for prop in s.properties()
        {
            properties.insert(prop.clone(),
                s
                    .get_property(prop)
                    .await
                    .map_err(|e| propagate_error(ErrorMessages::E_ACCESS_PROP,e))?
                    .clone()
            );
        }

        let service_name = s.service_name().await.to_string();

        srvc.insert(service_name.clone(), RemoteService{
            name: service_name,
            properties,
            active: s.is_active().await.map_err(|e| propagate_error(ErrorMessages::E_ACCESS_PROP,e))?
        });
    }

    Ok(Json(srvc))
}

async fn enable_disable_service(
    Path((action,service)): Path<(ServiceAction,String)>,
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Json(properties): Json<Option<HashMap<ServiceProperty, Value>>>
) -> Result<HTTPMessage,HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    let mut allowed_services:HashMap<String,&AbstractRemoteService> = HashMap::new();

    let (response_ok, response_err) = match action
    {
        ServiceAction::Enable => (SuccessMessages::S_ACCESS_ENABLED, ErrorMessages::E_ACCESS_ENABLED),
        ServiceAction::Disable => (SuccessMessages::S_ACCESS_DISABLED, ErrorMessages::E_ACCESS_DISABLED),
        ServiceAction::Update => (SuccessMessages::S_ACCESS_UPDATED, ErrorMessages::E_ACCESS_ENABLED),
    };
        
    for s in get_remote_services()
        .await
        .map_err(|e| propagate_error(response_err.clone(),e))?
        .iter()
    {
        allowed_services.insert(
            s.read().await.service_name().await.to_string(),
            s
        );
    }

    let requested_service = service.to_lowercase();
    let service_perm = UserPermissions::from_str(format!("services.{}.manage",requested_service).as_str());

    if !allowed_services.keys().cloned().collect::<Vec<String>>().contains(&requested_service) ||
        service_perm.is_err()
    {
        return Err(ErrorMessages::E_ACCESS_SERV_UNK.wrap_with_status_code(Some(
            vec![Value::from_str(requested_service.as_str()).unwrap()]
        )));
    }

    check_permission(&user, service_perm.unwrap()).await?;

    let service = allowed_services[&requested_service];

    if let Some(props) = properties
    {
        let mut s = service.write().await;
        for (prop,value) in props
        {
            s.set_property(prop.clone(),value)
                .await
                .map_err(|e| {
                    ErrorMessages::E_ACCESS_PROP.wrap_with_status_code(Some(
                        vec![
                            Value::String(prop.to_string()),
                            Value::String(e.to_string()),
                        ]
                    ))
                })?;
        }
    }

    service_manage(service, action).await?;

    Ok(response_ok.wrap_with_status_code(
        Some(vec![Value::String(requested_service.to_uppercase())])
    ))
}

pub fn get_route() -> Router<Arc<Backend>>
{
    Router::new().nest("/services",
                       Router::new()
                           .route("/get", get(list_access_services))
                           .route("/{action}/{service}",post(enable_disable_service))
    )
}