use axum::http::{HeaderMap, HeaderValue};
use axum_auth::AuthBearer;
use axum::Json;
use axum::routing::{Router, get, head, post};
use axum::extract::{State, Path};
use crate::backend::{Backend, FastAPIComp, HTTPMessage, User};
use crate::backend::jwt::TokenPurposes;
use std::sync::Arc;
use serde::Deserialize;
use serde_json::{json, Value};
use crate::backend::msg::{StatusMessage, SuccessMessages};
use crate::backend::permissions::{check_permission, UserPermissions};
use crate::backend::utils::MBoxMail;

const NOTIFICATION_HEADER:&str = "X-User-Notifications-Count";

#[derive(Debug, Deserialize)]
pub struct UsernameChange
{
    old_username:String,
    new_username: String
}

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

async fn get_user_notifications(AuthBearer(token): AuthBearer, State(backend):State<Arc<Backend>>) -> FastAPIComp<Vec<MBoxMail>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    let u = user.read().await;

    Ok(Json(u.get_notifications().await))
}

async fn get_user_notification_by_id(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Path(id): Path<String>
) -> FastAPIComp<Option<MBoxMail>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    let u = user.read().await;

    Ok(Json(u.get_notification_by_id(&id,true).await))
}

async fn get_all_users(AuthBearer(token): AuthBearer, State(backend):State<Arc<Backend>>) -> FastAPIComp<Value>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    let users = backend.get_users().await;

    if check_permission(&user, UserPermissions::UsersAccountManage).await.is_ok()
    {
        Ok(Json(json!(users)))
    }
    else
    {
        Ok(Json(json!(users.iter().map(|u| u.username.to_string()).collect::<Vec<_>>())))
    }
}

async fn get_unassociated_system_users(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>
) -> FastAPIComp<Vec<String>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::UsersAccountManage).await?;


    Ok(Json(backend.get_unassociated_sys_users().await?))
}

async fn assign_system_user(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Json(data): Json<UsernameChange>,
) -> Result<HTTPMessage, HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::UsersAccountManage).await?;

    backend.change_username(
        data.old_username.as_str(),
        data.new_username.as_str()
    ).await?;


    Ok(SuccessMessages::S_USER_NAME.wrap_with_status_code(None))
}

pub fn get_route() -> Router<Arc<Backend>>
{
    Router::new().nest("/users",
        Router::new()
        .route("/get", get(get_logged_user))
        .route("/get/sys", get(get_unassociated_system_users))
        .route("/get/all", get(get_all_users))
        .route("/get/notifications", head(get_user_notification_count))
        .route("/get/notifications", get(get_user_notifications))
        .route("/get/notifications/{id}", get(get_user_notification_by_id))
        .route("/set/sys-user", post(assign_system_user))
    )
}