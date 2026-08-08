use axum::Router;
use backend::api::get_api;
use backend::get_backend;
use backend::utils::detect_distro_family;
use std::sync::Arc;
use tower_http::trace::TraceLayer;
use tower_http::trace::{DefaultMakeSpan, DefaultOnFailure, DefaultOnResponse};
use tracing::{Level, debug};
use tracing_subscriber::FmtSubscriber;

use crate::backend::msg::{LogErrors, LoggerMessages};

pub mod cmdl;
pub mod events;
pub mod task;
pub mod backend;
pub mod vfs;
pub mod sensors;
pub mod dev;
pub mod rpi;


#[cfg(not(tokio_unstable))]
fn logger_init()
{
    let subscriber = FmtSubscriber::builder()
        .with_ansi(true)
        .with_level(true)
        .with_thread_names(true)
        .with_writer(std::io::stderr)
        .with_max_level(Level::DEBUG)
        .with_target(false)
        .finish();

    tracing::subscriber::set_global_default(subscriber)
        .expect("setting default subscriber failed");
}

#[cfg(tokio_unstable)]
fn logger_init()
{
    console_subscriber::Builder::default()
        .with_default_env()
        .init();

}

#[tokio::main]
async fn main()
{
    logger_init();

    let backend = get_backend().await;

    let app = Router::new()
        .merge(get_api())
        .layer(
            TraceLayer::new_for_http()
                .make_span_with(DefaultMakeSpan::new().level(Level::INFO))
                .on_response(DefaultOnResponse::new().level(Level::INFO))
                .on_failure(DefaultOnFailure::new().level(Level::ERROR))
        )
        .with_state(Arc::clone(&backend));

    debug!("OS Family detected: {}",detect_distro_family());
        


    let addr = backend.get_bind_addr().await;

    

    let listener = tokio::net::TcpListener::bind(
        addr.to_string()
    ).await;

    match listener
    {
        Ok(t) => axum::serve(t,app.into_make_service_with_connect_info::<std::net::SocketAddr>()).await.unwrap(),        
        Err(e) => LoggerMessages::Error(LogErrors::ServerCannotStart(&e.to_string())).log(),
    }
}
