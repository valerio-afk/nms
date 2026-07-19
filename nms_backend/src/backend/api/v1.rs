use axum::Router;
use std::sync::Arc;
use axum::{Json,http::StatusCode};
use msg::{WrappedResponse};

use crate::backend::Backend;

mod auth;
pub mod msg;
pub mod jwt;

type FastAPIComp<T> = Result<Json<T>, (StatusCode, Json<WrappedResponse>)>; //this type is to make it more compatible with the current frontend

pub fn v1_api() -> Router<Arc<Backend>>
{
    Router::new().nest(
        "/v1",
        Router::new().merge(auth::get_route())
    )
    
}
