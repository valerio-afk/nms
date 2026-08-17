use std::collections::HashMap;
use std::net::Ipv4Addr;
use crate::backend::net::{IPv4, NetworkInterface, read_wireguard_config_file, IfaceType};
use crate::backend::{propagate_error, Backend, DDNSProvider, FastAPIComp, IfaceStatusAction, HTTPMessage};
use crate::backend::permissions::{UserPermissions, check_permission};
use crate::backend::jwt::TokenPurposes;
use axum::extract::{State, Path, Query};
use axum::Router;
use axum::routing::{get, post, patch, delete};
use axum::Json;
use axum_auth::AuthBearer;
use ipnet::Ipv4Net;
use std::sync::Arc;
use serde::Deserialize;
use serde_json::Value;
use crate::backend::config::CfgDynDNS;
use crate::backend::msg::{StatusMessage, SuccessMessages};
use crate::backend::net::get_network_ifaces;
use super::msg::ErrorMessages;


#[derive(Clone,Deserialize)]
struct VPNConf
{
    pub address: Ipv4Addr,
    pub netmask: Ipv4Addr,
    pub endpoint:Ipv4Addr
}

#[derive(Clone,Deserialize)]
struct VPNPeer
{
    pub name: String,
    pub public_key: String
}

#[derive(Clone,Deserialize)]
struct VPNPeerDelete
{
    pub name: String,
}

#[derive(Clone,Deserialize)]
pub struct DDNSNewProvider
{
    pub name: String,
    pub proto: String,
    pub server: Option<String>,
    pub username: Option<String>,
    pub password: Option<String>,
    pub hostname: Option<String>,
}




async fn net_ifaces(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<Vec<NetworkInterface>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;

    check_permission(&user, UserPermissions::ClientDashboardNetworks).await?;

    let ifaces = get_network_ifaces().await;

    Ok(Json(ifaces))
}

async fn net_get_vpn_config(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<NetworkInterface>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::ClientDashboardNetworks).await?;

    let wg = read_wireguard_config_file()
        .await
        .map_err(|_| propagate_error(ErrorMessages::E_NET_VPN_CONF, anyhow::Error::msg("Unable to read wireguard configuration file")))?;

    let ip: Option<Ipv4Net> = if let Some(addr) = wg.get("Interface","Address")
    {
        if let Ok(addr) = addr.parse::<Ipv4Net>()
        {
            Some(addr)
        }
        else { None }
    }
    else { None };

    let ipv4:Option<IPv4> = match ip
    {
        Some(i) => Some(IPv4 {
            dynamic: false,
            address: Some(i.addr()),
            netmask: Some(i.netmask()),
            gateway: None,
            dns: vec![]
        }),
        None => None
    };


    Ok(Json(NetworkInterface {
        name: "vpn".to_string(),
        enabled: backend.is_vpn_active().await?,
        ipv4 ,
        ipv6: None,
        network_name: "VPN".to_string(),
        iface_type: IfaceType::VPN,
        has_profile: false,
        ap: None }))
}

async fn get_vpn_peers(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<Vec<(String, String)>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::NetworkVpnManage).await?;

    Ok(
        Json(backend
            .get_vpn_peers()
            .await?
            .iter()
            .map(|v| (v.name.clone(),v.ip.to_string()))
            .collect::<Vec<(String,String)>>()
    ))
}

async fn get_ddns_providers(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<HashMap<String, CfgDynDNS>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::NetworkDdnsManage).await?;

    Ok(Json(backend.get_ddns_cfgs().await))
}

async fn _add_ddns_provider(
    token: String,
    backend: Arc<Backend>,
    cfg : DDNSNewProvider,
    force:bool
) -> Result<HTTPMessage,HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::NetworkDdnsManage).await?;

    backend.add_ddns_service(
        cfg.name.as_str(),
        true,
        cfg.proto,
        cfg.server,
        cfg.username,
        cfg.password,
        cfg.hostname,
        force
    ).await?;

    Ok(SuccessMessages::S_NET_DDNS_ENABLED.wrap_with_status_code(
        Some(vec![Value::String(cfg.name)])
    ))
}

async fn add_ddns_provider(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>,
    Json(cfg) : Json<DDNSNewProvider>
) -> Result<HTTPMessage,HTTPMessage>
{
    _add_ddns_provider(token, backend, cfg, false).await
}

async fn edit_ddns_provider(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>,
    Json(cfg) : Json<DDNSNewProvider>
) -> Result<HTTPMessage,HTTPMessage>
{
    _add_ddns_provider(token, backend, cfg, true).await
}
//
// async fn start_ddns_provider(
//     Path(provider): Path<String>,
//     AuthBearer(token): AuthBearer,
//     State(backend): State<Arc<Backend>>,
//     credentials: Option<Json<DDNSCredentials>>
// ) -> Result<HTTPMessage,HTTPMessage>
// {
//     let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
//     let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
//     check_permission(&user, UserPermissions::NetworkDdnsManage).await?;
//
//
//     if let Some(Json(c)) = credentials && let Some(pwd) = c.password
//     {
//         backend.set_ddns_provider_credentials(
//             provider.as_str(),
//             c.username,
//             pwd,
//             true,
//         ).await?;
//     }
//     else
//     {
//         backend.enable_ddns_provider(provider.as_str(), true).await?;
//     }
//
//     Ok(SuccessMessages::S_NET_DDNS_ENABLED.wrap_with_status_code(
//         Some(vec![Value::String(provider)])
//     ))
// }
//
async fn delete_ddns_provider(
    Path(provider): Path<String>,
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> Result<HTTPMessage,HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::NetworkDdnsManage).await?;

    backend.remove_ddns_service(provider.as_str()).await?;

    Ok(SuccessMessages::S_NET_DDNS_DISABLED.wrap_with_status_code(
        Some(vec![Value::String(provider)])
    ))
}

async fn get_vpn_endpoint(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<Option<Ipv4Addr>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::NetworkVpnManage).await?;


    Ok(Json(backend.get_vpn_endpoint().await))
}

async fn vpn_config(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>,
    Json(cfg): Json<VPNConf>
) -> Result<HTTPMessage,HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::NetworkVpnManage).await?;


    backend.set_vpn_config(
        cfg.address,
        cfg.netmask,
        cfg.endpoint
    ).await?;

    Ok(SuccessMessages::S_NET_VPN_CONFIG.wrap_with_status_code(None))
}

async fn vpn_genkeys(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>,
) -> Result<HTTPMessage,HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::NetworkVpnManage).await?;

    backend.vpn_genkeys().await?;

    Ok(SuccessMessages::S_NET_VPN_KEYSGEN.wrap_with_status_code(None))
}

async fn get_vpn_pubkey(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>,
) -> FastAPIComp<Option<String>>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::NetworkVpnManage).await?;

    Ok(Json(backend.get_vpn_public_key().await))
}

async fn vpn_add_peer(
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>,
    Json(peer): Json<VPNPeer>
) -> Result<HTTPMessage,HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::NetworkVpnManage).await?;

    backend.add_vpn_peer(&peer.name,peer.public_key).await?;

    Ok(SuccessMessages::S_NET_VPN_PEER_ADDED.wrap_with_status_code(Some(vec![Value::String(peer.name)])))
}

async fn vpn_delete_peer(
    Query(peer): Query<VPNPeerDelete>,
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>,
) -> Result<HTTPMessage,HTTPMessage>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;
    check_permission(&user, UserPermissions::NetworkVpnManage).await?;

    backend.remove_vpn_peer(peer.name.as_str()).await?;

    Ok(SuccessMessages::S_NET_VPN_PEER_DELETED.wrap_with_status_code(Some(vec![Value::String(peer.name)])))
}
async fn change_iface_status (
    Path((iface,action)): Path<(String, IfaceStatusAction)>,
    AuthBearer(token): AuthBearer,
    State(backend): State<Arc<Backend>>
) -> FastAPIComp<()>
{
    let jwt = backend.verify_token(&token, TokenPurposes::Login).await?;
    let user = backend.get_user(&jwt.claims.username.unwrap()).await?;


    if iface == "vpn"
    {
        check_permission(&user, UserPermissions::NetworkVpnManage).await?;
        match action
        {
            IfaceStatusAction::Up => backend.vpn_up().await?,
            IfaceStatusAction::Down => backend.vpn_down().await?,
        }
    }
    else
    {
        check_permission(&user, UserPermissions::NetworkIfaceManage).await?;
        match action
        {
            IfaceStatusAction::Up => backend.iface_up(iface).await?,
            IfaceStatusAction::Down => backend.iface_down(iface).await?,
        }
    }

    Ok(Json(()))
}


pub fn get_route() -> Router<Arc<Backend>>
{
   
    Router::new().nest("/net",
        Router::new()
        .route("/ddns", get(get_ddns_providers))
        .route("/ddns", post(add_ddns_provider))
        .route("/ddns", patch(edit_ddns_provider))
        .route("/ddns/{provider}", delete(delete_ddns_provider))
        // .route("/ddns/{provider}/stop", post(stop_ddns_provider))
        .route("/vpn", get(net_get_vpn_config))
        .route("/vpn", patch(vpn_config))
        .route("/vpn/gen-keys", post(vpn_genkeys))
        .route("/vpn/peers", get(get_vpn_peers))
        .route("/vpn/peers", post(vpn_add_peer))
        .route("/vpn/peers", delete(vpn_delete_peer))
        .route("/vpn/pubkey", get(get_vpn_pubkey))
        .route("/vpn/endpoint", get(get_vpn_endpoint))
        .route("/{iface}/{action}", post(change_iface_status))
        .route("/ifaces", get(net_ifaces))
    )


}

