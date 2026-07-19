use uuid::Uuid;
use chrono::Utc;
use jsonwebtoken::{encode, decode, EncodingKey, DecodingKey, Header,Validation};
use serde::{Deserialize,Serialize};
use axum::Json;
use crate::backend::api::v1::msg::StatusMessage;
use crate::backend::config::CfgToken;
use super::msg::{WrappedResponse, ErrorMessages};



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
    let uuid = Uuid::new_v4();

    let claims:CfgToken = CfgToken 
    { 
        purpose,
        username,
        expire_date 
    };

    let token = JWTClaim 
    {
        uuid:Uuid::new_v4().to_string(),
        claims: claims.clone()
    };

    Ok(Token
    {
        uuid: uuid.to_string(),
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
) -> Result<JWTClaim,Json<WrappedResponse>>
{
    let malformed_err = ErrorMessages::E_AUTH_MALFORMED.wrap(None).to_json();

    let result = decode::<JWTClaim>(
        &token,
        &DecodingKey::from_secret(secret),
        &Validation::default()
    );

    if result.is_err() {return Err(malformed_err); }

    let jwt = result.unwrap().claims;

    let claims = &jwt.claims;

    if claims.purpose != requested_purpose { return Err(malformed_err); }

    if claims.expire_date >= Utc::now().timestamp()
    {
        return Err(ErrorMessages::E_AUTH_EXPIRED.wrap(None).to_json());
    }

    Ok(jwt)   
}