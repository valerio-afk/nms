use std::sync::Arc;

use axum::Router;
use v1::v1_api;

use crate::backend::Backend;
mod v1;


pub fn get_api() -> Router<Arc<Backend>>
{
    Router::new().nest(
        "/api", 
        Router::new().merge(v1_api())
    )
}