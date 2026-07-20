use axum::Router;
use std::sync::Arc;
use crate::backend::Backend;

mod auth;

pub use crate::backend::FastAPIComp;
pub use crate::backend::jwt;
pub use crate::backend::msg;


pub fn v1_api() -> Router<Arc<Backend>>
{
    Router::new().nest(
        "/v1",
        Router::new().merge(auth::get_route())
    )
    
}
