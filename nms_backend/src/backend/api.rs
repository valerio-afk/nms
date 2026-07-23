use std::sync::Arc;
use std::fmt::Debug;
use serde_json::Value;
use axum::Router;
use serde::{Deserialize, Serialize};
use v1::v1_api;

use crate::backend::Backend;
pub mod v1;


#[derive(Debug,Serialize)]
pub struct BackendPropertyResponse<T>
where for<'a> T: Debug + Deserialize<'a> + Serialize
{
    property:T,
    value:Value,
}


pub fn get_api() -> Router<Arc<Backend>>
{
    Router::new().nest(
        "/api", 
        Router::new().merge(v1_api())
    )
}