use axum::{Json, Router, extract::{Path,State,Query}, routing::{get,patch}, http::{StatusCode}};
use crate::backend::{Backend, api::v1::auth};
use super::jwt::{PermissiveTokenParameter,TokenPurposes};
use serde_json::{Value};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use super::FastAPIComp;
use super::msg::{StatusMessage,ErrorMessages};
use tracing::{error,info};
use totp_rs::{Algorithm, Secret, TOTP};


#[derive(Debug,Deserialize, Serialize)]
enum AuthProperties
{
    #[serde(rename = "is_configured")]
    IsConfigured
}


#[derive(Debug,Serialize)]
struct AuthPropertyResponse
{
    property:AuthProperties,
    
    value:Value,
}

#[derive(Debug,Serialize)]
struct AuthUriResponse
{
    provisioning_uri:String
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


async fn auth_new_secret
(
    Query(token):Query<PermissiveTokenParameter>,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<AuthUriResponse>
{
    let t = token.token;
    let mut otp_already_configured = false;

    if t.is_none() && backend.is_otp_configured()
    {
        otp_already_configured = true;
    }

    let mut username:Option<String> = None;

    if let Some(tok) = t
    {
        let claims = backend.verify_token(&tok, TokenPurposes::FirstLogin);

        if let Err(e) = claims
        {
            return Err((
                StatusCode::UNAUTHORIZED,
                e)
            );
        }

        username = claims.unwrap().username;

        if let Some(ref u) = username
        {
            if backend.has_otp_secret(u)
            {   
                otp_already_configured = true;
            }
        }
    }


    if otp_already_configured
    {
        error!("OTP is already configured");
        return Err((
            StatusCode::UNAUTHORIZED,
            Json(
                ErrorMessages::E_AUTH_ALREADY_CONFIG.wrap(None)
            )
        ));
    }



    let secret = Secret::generate_secret().to_bytes();


    if let Err(e) = secret
    {
        error!("Unable to encode secret key: {e}");
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorMessages::E_UNKNOWN.wrap(None))
        ));
    }
    

    //TODO: add secret to a temp data structure

    let totp = TOTP::new(
        Algorithm::SHA1,
        8,                  // digits
        1,                  // skew
        30,                 // period
        secret.unwrap(),
        Some("NMS".to_string()), 
        {
            match username
            {
                Some(ref u) => u.clone(),
                None=> "".to_string()
            }
        }
    );

    if let Err(e) = totp
    {
        error!("Unable to generate OTP: {e}");
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorMessages::E_UNKNOWN.wrap(None))
        ));
    }

    match username
    {
        Some(ref u) => info!("New secret generated for `{u}`"),
        None => info!("New secret generated")
    }

    Ok(
        Json(AuthUriResponse{provisioning_uri: totp.unwrap().get_url()})
    )


}

pub fn get_route() -> Router<Arc<Backend>>
{
    Router::new().nest("/auth",
        Router::new()
        .route("/otp/get/{property}", get(get_auth_property))
        .route("/otp",patch(auth_new_secret))
    )
}