use axum::Router;
use std::sync::Arc;

use crate::backend::Backend;

mod auth;

pub fn v1_api() -> Router<Arc<Backend>>
{
    Router::new().nest(
        "/v1",
        Router::new().merge(auth::get_route())
    )
    
}
