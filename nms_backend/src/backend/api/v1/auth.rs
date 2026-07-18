use serde::{Deserialize, Serialize};
use std::sync::Arc;
use axum::{Json, Router, extract::{Path,State}, routing::get};
use crate::backend::Backend;
use serde_json::Value;

#[derive(Debug,Deserialize, Serialize)]
enum AuthProperties
{
    #[serde(rename = "is_configured")]
    IsConfigured
}

// impl std::fmt::Display for AuthProperties
// {
//     fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
//     {
//         match self
//         {
//             AuthProperties::IsConfigured => write!(f,"is_configured")
//         }    
//     }
// }


#[derive(Debug,Serialize)]
struct AuthPropertyResponse
{
    property:AuthProperties,
    
    value:Value,
}

async fn get_auth_property(
    Path(property):Path<AuthProperties>,
    State(backend): State<Arc<Backend>>
) -> Json<AuthPropertyResponse>
{
    Json(AuthPropertyResponse {
        property: property,
        value: Value::Bool(backend.is_otp_configured())
    })
}

pub fn get_route() -> Router<Arc<Backend>>
{
    Router::new().nest("/auth",
        Router::new()
        .route("/otp/get/{property}", get(get_auth_property))
    )
}