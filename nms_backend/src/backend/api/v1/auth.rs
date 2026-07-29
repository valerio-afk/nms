use axum::{Json, Router, debug_handler, extract::{Path,State,Query}, routing::{get,patch, post}};
use axum_auth::AuthBearer;
use crate::backend::{jwt::JWTClaim, permissions::{UserPermissions, check_permission}, Backend, TemporarySecret};
use crate::events::{Events,ContextVariables,Trigger, ContextBuilder};
use super::jwt::{PermissiveTokenParameter,TokenPurposes,create_token};
use serde_json::{Value};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use super::FastAPIComp;
use super::msg::{StatusMessage,ErrorMessages, LogErrors, LoggerMessages, LogInfos};
use std::error::Error;
use totp_rs::{Algorithm, Secret, TOTP};
use tower_governor::{
    GovernorLayer, governor::GovernorConfigBuilder, key_extractor::SmartIpKeyExtractor,
};
use crate::backend::api::BackendPropertyResponse;

const LOGIN_LIFETIME:i64 = 30*60;



#[derive(Debug,Deserialize, Serialize)]
enum AuthProperties
{
    #[serde(rename = "is_configured")]
    IsConfigured
}


#[derive(Debug,Serialize)]
struct AuthUriResponse
{
    provisioning_uri:String
}

#[derive(Debug,Serialize)]
struct AuthTokenResponse
{
    token:String,
    username:String,
    expire_date:i64
}

#[derive(Debug,Deserialize)]
struct OPTVerificationForm
{
    purpose:TokenPurposes,
    otp:String
}

fn verify_otp<'a>(otp:&'a str,secret:String,username:&'a Option<String>) -> Result<bool,Box<dyn Error + 'a + Send + Sync>>
{
    match Secret::Encoded(secret).to_bytes()
    {
        Ok(secret) => 
        {
            match TOTP::new(
                Algorithm::SHA1,
                6,                  // digits
                1,                  // skew
                30,                 // period
                secret,
                None,
                "".into()
            )
            {
                Ok(totp) => 
                {
                    match totp.check_current(otp)
                    {
                        Ok(r) => Ok(r),
                        Err(e) => Err(Box::new(e))
                    }
                }
                Err(e) => 
                {
                    LoggerMessages::Error(LogErrors::OTPInit(username, &e.to_string())).log();
                    return Err(Box::new(e));
                }
                
            }
        }
        Err(e) =>
        {
            LoggerMessages::Error(LogErrors::SecretEncoding(&e.to_string())).log();
            return Err(Box::new(e));
        } 
    }
}



async fn get_auth_property(
    Path(property):Path<AuthProperties>,
    State(backend): State<Arc<Backend>>
) -> Json<BackendPropertyResponse<AuthProperties>>
{
    Json(BackendPropertyResponse {
        property: property,
        value: Value::Bool(backend.is_otp_configured().await)
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

    if t.is_none() && backend.is_otp_configured().await
    {
        otp_already_configured = true;
    }

    let mut username:Option<String> = None;

    if let Some(tok) = t
    {
        let claims = backend.verify_token(&tok, TokenPurposes::FirstLogin).await?;

        username = claims.claims.username;

        if let Some(ref u) = username
        {
            if backend.has_otp_secret(u).await
            {   
                otp_already_configured = true;
            }
        }
    }


    if otp_already_configured
    {
        LoggerMessages::Error(LogErrors::OTPAlreadyConf(&username)).log();
        return Err(ErrorMessages::E_AUTH_ALREADY_CONFIG.wrap_with_status_code(None));
    }



    let secret = Secret::generate_secret().to_encoded();
    let secret_string = secret.to_string();
    let secret_bytes = secret.to_bytes();


    if let Err(e) = secret_bytes
    {
        LoggerMessages::Error(LogErrors::SecretEncoding(&e.to_string())).log();
        return Err(ErrorMessages::E_UNKNOWN.wrap_with_status_code(None));
    }
    


    let totp = TOTP::new(
        Algorithm::SHA1,
        6,                  // digits
        1,                  // skew
        30,                 // period
        secret_bytes.unwrap(),
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
        LoggerMessages::Error(LogErrors::NewTOTPURI(&e.to_string())).log();
        return Err(ErrorMessages::E_UNKNOWN.wrap_with_status_code(None));
    }

    LoggerMessages::Info(LogInfos::OTPSecretGen(&username)).log();

    backend.add_temporary_secret(username, secret_string).await;

    Ok(
        Json(AuthUriResponse{provisioning_uri: totp.unwrap().get_url()})
    )
}

#[debug_handler]

async fn auth_otp_verify
(
    State(backend):State<Arc<Backend>>,
    Json(otp):Json<OPTVerificationForm>
) -> FastAPIComp<AuthTokenResponse>
{
    let mut username:Option<String> = None;

    //I received an OTP to verify
    //I check if it's a user performing their first login by searching secrets in the temporary cache
    {
        let tmp_secrets:Vec<TemporarySecret> = backend.get_temporary_secrets().await;

        for tmp in tmp_secrets
        {
            match verify_otp(&otp.otp, tmp.secret, &tmp.username)
            {
                Ok(res) =>
                    {
                        if res
                        {
                            username = Some(backend.save_temporary_secret(&tmp.uuid).await?);
                            backend.flush_config().await?;
                            break;
                        }
                    }
                Err(e) => LoggerMessages::Error(LogErrors::TmpOTPVerification(&e.to_string())).log(),
            }
        }
    }


    if username.is_none()
    {
        //If the first bit failed, it could be a current user trying to login.
        let secrets = backend.get_otp_secrets().await;
        for (uname,secret) in secrets
        {
            let uname = Some(uname);

            if let Ok(res) = verify_otp(&otp.otp, secret, &uname.clone())
            {
                if res
                {
                    username = uname;
                }
            }
        }
    }

    if username.is_none()
    {
        LoggerMessages::Error(LogErrors::OTPWrong).log();
        return Err(ErrorMessages::E_AUTH_WRONG_OTP.wrap_with_status_code(None));
    }

    let user = backend.get_user(&username.as_ref().unwrap()).await?;

    check_permission(&user, UserPermissions::ClientDashboardAccess).await?;



    match create_token(
        username.clone(), 
        otp.purpose, 
        LOGIN_LIFETIME, //30 mins
        backend.secret_key.as_bytes()
    )
    {
        Ok(tok) => {

            let response = Json(AuthTokenResponse {
                token: tok.encoded_claims,
                username: tok.claims.username.clone().unwrap(),
                expire_date: tok.claims.exp
            });

            // backend.event_manager.trigger(
            //     Trigger::Event(Events::UserLoggedIn),
            //     ContextBuilder::from(ContextVariables::TriggerUser,tok.claims.username.clone().unwrap()).finish()
            // );

            backend.push_token(JWTClaim{
                uuid: tok.uuid,
                claims: tok.claims
            }).await;

            backend.flush_config().await?;

            return Ok(response);
        }
        Err(e) => {
            LoggerMessages::Error(LogErrors::LoginToken(&username, &e.to_string())).log();
            return Err(ErrorMessages::E_UNKNOWN.wrap_with_status_code(None));
        }
    }
}

async fn auth_token_refresh(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>
) -> FastAPIComp<AuthTokenResponse>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let username = jwt.claims.username.clone();

    match create_token(
        jwt.claims.username, 
        TokenPurposes::Login, 
        LOGIN_LIFETIME, //30 mins
        backend.secret_key.as_bytes()
    )
    {
        Ok(new_tok) => {

            let response = Json(AuthTokenResponse {
                token: new_tok.encoded_claims,
                username: new_tok.claims.username.clone().unwrap(),
                expire_date: new_tok.claims.exp
            });

            backend.revoke_token(&jwt.uuid).await;

            backend.push_token(JWTClaim{
                uuid: new_tok.uuid,
                claims: new_tok.claims
            }).await;

            backend.flush_config().await?;

            return Ok(response);
        }
        Err(e) => {
            LoggerMessages::Error(LogErrors::LoginToken(&username, &e.to_string())).log();
            return Err(ErrorMessages::E_UNKNOWN.wrap_with_status_code(None));
        }
    }    
}

async fn auth_logout(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>
) -> FastAPIComp<()>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    backend.revoke_token(&jwt.uuid).await;

    Ok(Json(()))
}

async fn auth_verify_first_login_token(
    Query(token): Query<String>,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<bool>
{
    let jwt = backend.verify_token(&token, TokenPurposes::FirstLogin).await?;

    match jwt.claims.username
    {
        Some(u) => Ok(Json(backend.has_otp_secret(&u).await)),
        None=> Err(ErrorMessages::E_AUTH_MALFORMED.wrap_with_status_code(None))
    }
}


pub fn get_route() -> Router<Arc<Backend>>
{
    let governor_limited = GovernorConfigBuilder::default()
        .per_second(1)
        .burst_size(5)
        .key_extractor(SmartIpKeyExtractor)
        .finish()
        .unwrap();

    let limited_endpoints = Router::new()
        .route("/otp",patch(auth_new_secret))
        .route("/otp",post(auth_otp_verify))
        .route("/otp/refresh",post(auth_token_refresh))
        .layer(GovernorLayer::new (governor_limited));

    Router::new().nest("/auth",
        Router::new()
        .route("/otp/get/{property}", get(get_auth_property))
        .route("/token/first_login",get(auth_verify_first_login_token))
        .route("/logout",post(auth_logout))
        .merge(limited_endpoints)
    )
}