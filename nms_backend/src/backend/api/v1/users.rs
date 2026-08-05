use axum::http::{HeaderMap, HeaderValue};
use axum_auth::AuthBearer;
use axum::Json;
use axum::routing::{Router, get, head};
use axum::extract::State;
use crate::backend::{Backend, FastAPIComp, HTTPMessage, User};
use crate::backend::jwt::TokenPurposes;
use std::sync::Arc;

const NOTIFICATION_HEADER:&str = "X-User-Notifications-Count";

async fn get_logged_user(AuthBearer(token): AuthBearer, State(backend):State<Arc<Backend>>) -> FastAPIComp<Option<User>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;

    match jwt.claims.username
    {
        Some(u) =>
        {
            let user = backend.get_user(&u).await?;
            let usr = user.read().await;

            Ok(Json(Some(usr.clone())))
        }
        None => Ok(Json(None))
    }
}

async fn get_user_notification_count(AuthBearer(token): AuthBearer, State(backend):State<Arc<Backend>>) -> Result<HeaderMap, HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    let mut headers = HeaderMap::new();

    let u = user.read().await;
    

    headers.insert(NOTIFICATION_HEADER, HeaderValue::from(u.notifications));

    Ok(headers)
}


pub fn get_route() -> Router<Arc<Backend>>
{
    Router::new().nest("/users",
        Router::new()
        .route("/get", get(get_logged_user))
        .route("/get/notifications", head(get_user_notification_count))
    )
}