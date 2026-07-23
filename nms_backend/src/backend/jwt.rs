use uuid::Uuid;
use chrono::Utc;
use jsonwebtoken::{encode, decode, EncodingKey, DecodingKey, Header,Validation, errors::{Error,ErrorKind}};
use serde::{Deserialize,Serialize};
use crate::backend::api::v1::msg::StatusMessage;
use crate::backend::config::CfgToken;
use crate::backend::msg::{LoggerMessages,LogErrors};
use super::msg::{ErrorMessages};
use super::HTTPError;



#[derive(Debug, Deserialize, Serialize)]
pub struct PermissiveTokenParameter
{
    pub token: Option<String>
}

#[derive(Debug, Deserialize, Serialize)]
pub struct TokenParameter
{
    pub token: String
}

#[derive(Debug, Deserialize, Serialize, Clone, PartialEq)]
pub enum TokenPurposes
{
    #[serde(rename = "login")]
    Login,

    #[serde(rename = "first_login")]
    FirstLogin
}

#[derive(Debug, Deserialize, Serialize)]
pub struct JWTClaim
{
    pub uuid:String,
    
    #[serde(flatten)]
    pub claims: CfgToken
}

pub struct Token
{
    pub uuid:String,
    pub encoded_claims:String,
    pub claims:CfgToken
}

pub fn create_token
(
    username:Option<String>,
    purpose:TokenPurposes,
    duration:i64,
    secret: &[u8]
) -> Result<Token,jsonwebtoken::errors::Error>
{

    let expire_date = Utc::now().timestamp() + duration;
    let uuid = Uuid::new_v4().to_string();

    let claims:CfgToken = CfgToken 
    { 
        purpose,
        username,
        exp: expire_date 
    };

    let token = JWTClaim 
    {
        uuid: uuid.clone(),
        claims: claims.clone()
    };

    Ok(Token
    {
        uuid: uuid,
        encoded_claims: encode(
            &Header::default(),
            &token,
            &EncodingKey::from_secret(secret),
        )?,
        claims:claims
    })
}

pub fn token_verification(
    token:&str,
    requested_purpose:TokenPurposes,
    secret:&[u8]
) -> Result<JWTClaim,HTTPError>
{

    let tok = decode::<JWTClaim>(
        &token,
        &DecodingKey::from_secret(secret),
        &Validation::default()
    ).map_err(|e:Error| {
        match e.kind()
        {
            ErrorKind::ExpiredSignature => ErrorMessages::E_AUTH_EXPIRED.wrap_with_status_code(None),
            _ =>
            {
                LoggerMessages::Error(LogErrors::UnexpectedJWT(&format!("{}",e))).log();
                ErrorMessages::E_AUTH_MALFORMED.wrap_with_status_code(None)
            }
        }
    })?;


    let jwt = tok.claims;

    let claims = &jwt.claims;

    if claims.purpose != requested_purpose 
    {
        return Err(ErrorMessages::E_AUTH_INVALID.wrap_with_status_code(None));
    }

    Ok(jwt)   
}