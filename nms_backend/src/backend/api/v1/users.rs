use axum::http::{HeaderMap, HeaderValue};
use axum_auth::AuthBearer;
use axum::Json;
use axum::routing::{Router, get, head, post, delete};
use axum::extract::{State, Path};
use crate::backend::{Backend, FastAPIComp, HTTPMessage, HomeDirAction, User};
use crate::backend::jwt::TokenPurposes;
use std::sync::{Arc};
use serde::Deserialize;
use serde_json::{json, Value};
use crate::backend::msg::{StatusMessage, SuccessMessages};
use crate::backend::permissions::{check_permission, UserPermissions};
use crate::backend::utils::{InboxMail, NOTIFICATION_READ_HEADER};
use tokio::sync::{RwLock};



async fn allow_self_change(current_user:Arc<RwLock<User>>, target_username:&str) -> Result<(),HTTPMessage>
{
    if current_user.read().await.username != target_username { check_permission(&current_user, UserPermissions::UsersAccountManage).await?; }

    Ok(())
}
#[derive(Debug, Deserialize)]
pub struct UsernameChange
{
    old_username:String,
    new_username: String
}

#[derive(Debug, Deserialize)]
pub struct FullnameChange
{
    username:String,
    fullname:String
}

#[derive(Debug, Deserialize)]
pub struct UIDChange
{
    username:String,
    uid: u32
}

#[derive(Debug, Deserialize)]
pub struct SudoChange
{
    username:String,
    sudo: bool
}

#[derive(Debug, Deserialize)]
pub struct QuotaChange
{
    username:String,
    quota: String
}

#[derive(Debug, Deserialize)]
pub struct PermissionsChange
{
    username:String,
    permissions: Vec<String>
}

#[derive(Debug, Deserialize)]
pub struct AccessServicePasswordChange
{
    username:String,
    password: String
}

#[derive(Debug, Deserialize)]
pub struct NewUserProfile
{
    username:String,
    visible_name: Option<String>,
    permissions:Vec<String>,
    quota: Option<String>,
    sudo: bool
}

#[derive(Debug, Deserialize)]
pub struct DeleteUser
{
    username:String,
    home_files: HomeDirAction,
    move_to: Option<String>
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
    

    headers.insert(NOTIFICATION_READ_HEADER, HeaderValue::from(u.notifications));

    Ok(headers)
}

async fn get_user_notifications(AuthBearer(token): AuthBearer, State(backend):State<Arc<Backend>>) -> FastAPIComp<Vec<InboxMail>>
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
) -> FastAPIComp<Option<InboxMail>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    let u = user.read().await;

    Ok(Json(u.get_notification_by_id(&id,true).await))
}

async fn delete_user_notification_by_id(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Path(id): Path<String>
) -> FastAPIComp<()>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    let u = user.read().await;

    u.delete_notification_by_id(id.as_str()).await;

    Ok(Json(()))
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

async fn change_username_internal(
    token: String,
    backend:Arc<Backend>,
    data: UsernameChange,
    change_sys_user:bool
) -> Result<HTTPMessage, HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::UsersAccountManage).await?;
    

    backend.change_username(
        data.old_username.as_str(),
        data.new_username.as_str(),
        change_sys_user
    ).await?;


    Ok(SuccessMessages::S_USER_NAME.wrap_with_status_code(None))
}

async fn assign_system_user(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Json(data): Json<UsernameChange>
) -> Result<HTTPMessage, HTTPMessage>
{
    change_username_internal(token, backend, data, false).await
}

async fn change_username(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Json(data): Json<UsernameChange>
) -> Result<HTTPMessage, HTTPMessage>
{
    change_username_internal(token, backend, data, true).await
}


async fn new_user(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Json(data): Json<NewUserProfile>,
) -> Result<HTTPMessage, HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::UsersAccountManage).await?;

    backend.add_user(
        data.username.clone(),
        data.visible_name,
        data.permissions,
        data.quota,
        data.sudo
    ).await?;

    Ok(SuccessMessages::S_NEW_USER.wrap_with_status_code(
        Some(vec![Value::String(data.username)])
    ))
}

async fn set_visible_name(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Json(data): Json<FullnameChange>,
) -> Result<HTTPMessage, HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    allow_self_change(user, &data.username).await?;

    backend.change_fullname(
        data.username.as_str(),
        data.fullname.as_str()
    ).await?;


    Ok(SuccessMessages::S_USER_FULLNAME.wrap_with_status_code(None))
}

async fn set_uid(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Json(data): Json<UIDChange>,
) -> Result<HTTPMessage, HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::UsersAccountManage).await?;

    backend.change_uid(
        data.username.as_str(),
        data.uid
    ).await?;


    Ok(SuccessMessages::S_USER_UID.wrap_with_status_code(None))
}

async fn set_sudo(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Json(data): Json<SudoChange>,
) -> Result<HTTPMessage, HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::UsersAccountManage).await?;

    backend.set_sudo_group(
        data.username.as_str(),
        data.sudo
    ).await?;


    Ok(SuccessMessages::S_USER_SUDO.wrap_with_status_code(None))
}

async fn set_quota(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Json(data): Json<QuotaChange>,
) -> Result<HTTPMessage, HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::UsersAccountManage).await?;

    backend.set_user_quota(
        data.username.as_str(),
        Some(data.quota)
    ).await?;

    Ok(SuccessMessages::S_USER_QUOTA.wrap_with_status_code(None))
}

async fn change_pwd_service(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Path(svc): Path<String>,
    Json(data): Json<AccessServicePasswordChange>
) -> Result<HTTPMessage, HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    allow_self_change(user, &data.username).await?;

    backend.access_service_change_password(&svc,&data.username,&data.password).await?;

    Ok(SuccessMessages::S_USER_PASSWORD.wrap_with_status_code(None))
}


async fn set_permissions(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Json(data): Json<PermissionsChange>,
) -> Result<HTTPMessage, HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::UsersAccountManage).await?;

    backend.set_user_permissions(
        data.username.as_str(),
        data.permissions
    ).await?;

    Ok(SuccessMessages::S_USER_PERM.wrap_with_status_code(None))
}

async fn delete_user(
    AuthBearer(token): AuthBearer,
    State(backend):State<Arc<Backend>>,
    Json(data): Json<DeleteUser>,
) -> Result<HTTPMessage, HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::UsersAccountManage).await?;

    backend.delete_user(
        data.username.as_str(),
        data.home_files,
        data.move_to.as_deref()
    ).await?;

    Ok(SuccessMessages::S_DEL_USER.wrap_with_status_code(
        Some(vec![
            Value::String(data.username)
        ])
    ))
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
        .route("/get/notifications/{id}", delete(delete_user_notification_by_id))
        .route("/set/sys-user", post(assign_system_user))
        .route("/set/fullname", post(set_visible_name))
        .route("/set/permissions", post(set_permissions))
        .route("/set/uid", post(set_uid))
        .route("/set/sudo", post(set_sudo))
        .route("/set/username", post(change_username))
        .route("/set/quota", post(set_quota))
        .route("/new", post(new_user))
        .route("/delete", post(delete_user))
        .route("/service/{svc}", post(change_pwd_service))
    )
}