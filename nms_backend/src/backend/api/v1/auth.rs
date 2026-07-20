use axum::{Json, Router, extract::{Path,State,Query, Form}, routing::{get,patch, post}};
use crate::{backend::{Backend, jwt::JWTClaim, permissions::{UserPermissions, check_permission}}};
use crate::events::{Events,ContextVariables,Trigger, ContextBuilder};
use super::jwt::{PermissiveTokenParameter,TokenPurposes,create_token};
use serde_json::{Value};
use serde::{Deserialize, Serialize};
use std::{collections::hash_map, sync::Arc};
use super::FastAPIComp;
use super::msg::{StatusMessage,ErrorMessages, LogErrors, LoggerMessages, LogInfos};
use std::error::Error;
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

fn verify_otp<'a>(otp:&'a str,secret:String,username:&'a Option<String>) -> Result<bool,Box<dyn Error + 'a>>
{
    match Secret::Encoded(secret).to_bytes()
    {
        Ok(secret) => 
        {
            match TOTP::new(
                Algorithm::SHA1,
                8,                  // digits
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
        let claims = backend.verify_token(&tok, TokenPurposes::FirstLogin)?;

        username = claims.username;

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
        LoggerMessages::Error(LogErrors::OTPAlreadyConf(&username)).log();
        return Err(ErrorMessages::E_AUTH_ALREADY_CONFIG.wrap_with_status_code(None));
    }



    let secret = Secret::generate_secret();
    let secret_string = secret.to_string();
    let secret_bytes = secret.to_bytes();


    if let Err(e) = secret_bytes
    {
        LoggerMessages::Error(LogErrors::SecretEncoding(&e.to_string())).log();
        return Err(ErrorMessages::E_UNKNOWN.wrap_with_status_code(None));
    }
    


    let totp = TOTP::new(
        Algorithm::SHA1,
        8,                  // digits
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

    backend.add_temporary_secret(username, secret_string);

    Ok(
        Json(AuthUriResponse{provisioning_uri: totp.unwrap().get_url()})
    )
}

async fn auth_otp_verify
(
    State(backend):State<Arc<Backend>>,
    Form(otp):Form<OPTVerificationForm>
) -> FastAPIComp<AuthTokenResponse>
{
    let mut username:Option<String> = None;

    //I received an OTP to verify
    //I check if it's a user performing their first login by searching secrets in the temporary cache
    if let Ok(tmp_secrets) = backend.get_temporary_secrets()
    {
        for tmp in tmp_secrets
        {
            match verify_otp(&otp.otp, tmp.secret, &tmp.username)
            {
                Ok(res) =>
                {
                    if res
                    {
                        username = Some(backend.save_temporary_secret(&tmp.uuid)?);
                        backend.flush_config();
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
        for (uname,secret) in backend.get_otp_secrets()?
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

    let user = backend.get_user(&username.as_ref().unwrap())?;

    check_permission(&user.permissions, UserPermissions::ClientDashboardAccess)?;



    match create_token(
        username, 
        TokenPurposes::Login, 
        60*30, //30 mins
        backend.secret_key.as_bytes()
    )
    {
        Ok(tok) => {

            let response = Json(AuthTokenResponse {
                token: tok.encoded_claims,
                username: tok.claims.username.clone().unwrap(),
                expire_date: tok.claims.expire_date
            });

            backend.event_manager.trigger(
                Trigger::Event(Events::UserLoggedIn),
                ContextBuilder::from(ContextVariables::TriggerUser,tok.claims.username.clone().unwrap()).finish()
            );

            backend.push_token(JWTClaim{
                uuid: tok.uuid,
                claims: tok.claims
            });

            return Ok(response);
        }
        Err(e) => {
            LoggerMessages::Error(LogErrors::LoginToken(&user.username, &e.to_string())).log();
            return Err(ErrorMessages::E_UNKNOWN.wrap_with_status_code(None));
        }
    }



}

pub fn get_route() -> Router<Arc<Backend>>
{
    Router::new().nest("/auth",
        Router::new()
        .route("/otp/get/{property}", get(get_auth_property))
        .route("/otp",patch(auth_new_secret))
        .route("/otp",post(auth_otp_verify))
    )
}