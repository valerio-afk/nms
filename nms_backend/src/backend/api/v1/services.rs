use std::collections::HashMap;
use indexmap::IndexMap;
use std::sync::Arc;
use axum::extract::State;
use axum::{Router, Json};
use axum::routing::get;
use axum_auth::AuthBearer;
use crate::backend::{propagate_error, Backend, FastAPIComp, propagate_unknown_error};
use crate::backend::jwt::TokenPurposes;
use crate::backend::permissions::{check_permission, UserPermissions};
use crate::backend::remote_access::{get_remote_services, ServiceProperty};
use serde_json::Value;
use serde::Serialize;
use crate::backend::msg::ErrorMessages;

#[derive(Serialize, Debug)]
struct RemoteService
{
    name:String,
    properties: HashMap<ServiceProperty, Value>,
    active:bool
}

async fn list_access_services(AuthBearer(token): AuthBearer, State(backend):State<Arc<Backend>>) -> FastAPIComp<IndexMap<String,RemoteService>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::ClientDashboardAccess).await?;

    let mut remote_srv = get_remote_services()
        .await
        .map_err(|e| propagate_unknown_error(e))?
        .write()
        .await;

    let mut srvc:IndexMap<String,RemoteService> = IndexMap::new();

    for s in remote_srv.iter_mut()
    {
        let mut properties:HashMap<ServiceProperty,Value> = HashMap::new();

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

        srvc.insert(s.service_name().to_string(), RemoteService{
            name: s.service_name().to_string(),
            properties: properties,
            active: s.is_active().await.map_err(|e| propagate_error(ErrorMessages::E_ACCESS_PROP,e))?
        });
    }

    Ok(Json(srvc))
}

pub fn get_route() -> Router<Arc<Backend>>
{
    Router::new().nest("/services",
                       Router::new()
                           .route("/get", get(list_access_services))
    )
}