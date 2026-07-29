use crate::backend::net::{IPv4, NetworkInterface, read_wireguard_config_file, IfaceType};
use crate::backend::{Backend, FastAPIComp, propagate_error};
use crate::backend::permissions::{UserPermissions, check_permission};
use crate::backend::jwt::TokenPurposes;
use axum::extract::{State};
use axum::Router;
use axum::routing::get;
use axum::Json;
use axum_auth::AuthBearer;
use ipnet::Ipv4Net;
use std::sync::Arc;
use crate::backend::net::get_network_ifaces;
use super::msg::ErrorMessages;


#[axum::debug_handler]
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
        enabled: false,
        ipv4: ipv4 ,
        ipv6: None,
        network_name: "VPN".to_string(),
        iface_type: IfaceType::VPN,
        has_profile: false,
        ap: None }))
}

pub fn get_route() -> Router<Arc<Backend>>
{
   
    Router::new().nest("/net",
        Router::new()
        .route("/ifaces", get(net_ifaces))
        .route("/vpn", get(net_get_vpn_config))
    )


}

