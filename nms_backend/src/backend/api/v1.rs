use axum::Router;
use std::sync::Arc;
use crate::backend::Backend;

mod auth;
mod users;
mod system;
mod pool;
mod disks;
mod net;
mod services;

pub use crate::backend::FastAPIComp;
pub use crate::backend::jwt;
pub use crate::backend::msg;


pub fn v1_api() -> Router<Arc<Backend>>
{
    Router::new().nest(
        "/v1",
        Router::new()
            .merge(auth::get_route())
            .merge(users::get_route())
            .merge(system::get_route())
            .merge(pool::get_route())
            .merge(disks::get_route())
            .merge(net::get_route())
            .merge(services::get_route())
    )
    
}
