use uuid::Uuid;
use chrono::Utc;
use jsonwebtoken::{encode, EncodingKey, Header};
use serde::{Deserialize,Serialize};

use crate::backend::config::CfgToken;

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