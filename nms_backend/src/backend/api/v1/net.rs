use crate::backend::net::NetworkInterface;
use crate::backend::{Backend, FastAPIComp};
use crate::backend::permissions::{UserPermissions, check_permission};
use crate::backend::jwt::TokenPurposes;
use axum::extract::{State};
use axum::Router;
use axum::routing::get;
use axum::Json;
use axum_auth::AuthBearer;
use std::sync::Arc;
use crate::backend::net::get_network_ifaces;


async fn net_ifaces(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<Vec<NetworkInterface>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login)?;
    let user = backend.get_user(&jwt.claims.username.unwrap())?;

    check_permission(&user, UserPermissions::ClientDashboardNetworks)?;

    let ifaces = get_network_ifaces();

    println!("{:?}",ifaces);

    Ok(Json(ifaces))
}

pub fn get_route() -> Router<Arc<Backend>>
{
   
    Router::new().nest("/net",
        Router::new()
        .route("/ifaces", get(net_ifaces))
    )
}