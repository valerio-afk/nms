use axum::http::{HeaderMap, HeaderValue};
use axum_auth::AuthBearer;
use axum::Json;
use axum::routing::{Router, get, head};
use axum::extract::State;
use crate::backend::{Backend, FastAPIComp, HTTPError, User};
use crate::backend::jwt::TokenPurposes;
use crate::backend::msg::{LoggerMessages,LogErrors, ErrorMessages, StatusMessage};
use std::sync::Arc;

const NOTIFICATION_HEADER:&str = "X-User-Notifications-Count";

async fn get_logged_user(AuthBearer(token): AuthBearer, State(backend):State<Arc<Backend>>) -> FastAPIComp<Option<User>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login)?;

    match jwt.claims.username
    {
        Some(u) =>
        {
            let user = backend.get_user(&u)?;

            Ok(
                Json(
                    Some(
                        (*user).read().map_err(|e|
                                {
                                    LoggerMessages::Error(LogErrors::UserReadLock(&e.to_string()));
                                    ErrorMessages::E_UNKNOWN.wrap_with_status_code(None)
                                }
                            )?.clone()
                        )
                    )
            )
        }
        None => Ok(Json(None))
    }
}

async fn get_user_notification_count(AuthBearer(token): AuthBearer, State(backend):State<Arc<Backend>>) -> Result<HeaderMap,HTTPError>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login)?;
    let user = backend.get_user(&jwt.claims.username.unwrap())?;
    let mut headers = HeaderMap::new();

    let notif = match user.read()
    {
        Ok(u) => u.notifications,
        Err(_) => 0
    };

    headers.insert(NOTIFICATION_HEADER, HeaderValue::from(notif));

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