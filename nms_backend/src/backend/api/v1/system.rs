use axum_auth::AuthBearer;
use axum::Json;
use axum::routing::{Router, get};
use axum::extract::State;
use crate::backend::{Backend, FastAPIComp};
use crate::backend::jwt::TokenPurposes;
use crate::backend::permissions::{UserPermissions, check_permission};
use std::sync::Arc;

async fn test(AuthBearer(token): AuthBearer, State(backend):State<Arc<Backend>>) -> FastAPIComp<()>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login)?;
    let user = backend.get_user(&jwt.claims.username.unwrap())?;

    check_permission(&user, UserPermissions::ClientDashboardAccess)?;

    Ok(Json(()))
}


pub fn get_route() -> Router<Arc<Backend>>
{
    Router::new().nest("/system",
        Router::new()
        .route("/test", get(test))
    )
}