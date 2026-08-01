use tracing::{Level,debug};
use tracing_subscriber::FmtSubscriber;
use backend::get_backend;
use backend::utils::detect_distro_family;
use backend::api::get_api;
use tower_http::trace::TraceLayer;
use tower_http::trace::{DefaultMakeSpan,DefaultOnResponse,DefaultOnFailure};
use std::sync::{Arc};
use axum::{Router};

use crate::backend::msg::{LoggerMessages,LogErrors};

pub mod cmdl;
pub mod events;
pub mod task;
pub mod backend;
pub mod vfs;


// tracing_subscriber::registry()
//         .with(
//             tracing_subscriber::EnvFilter::try_from_default_env()
//                 .unwrap_or_else(|_| "rest=debug,tower_http=debug,axum::rejection=trace".into()),
//         )
//         .with(tracing_subscriber::fmt::layer())
//         .init();
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


#[tokio::main]
async fn main() 
{
    logger_init();
    let backend = get_backend().await;

    let app = Router::new()
        .merge(get_api())
        // .layer(
        //     TraceLayer::new_for_http().make_span_with(
        //         |request: &Request<_>|
        //         {
        //             let matched_path = request
        //                 .extensions()
        //                 .get::<MatchedPath>()
        //                 .map(MatchedPath::as_str);

        //             debug_span!("http_request",
        //                 method = ?request.method(),
        //                 path = matched_path
        //             )
        //         }
        //     ).on_failure( 
        //         |error: ServerErrorsFailureClass, _latency: Duration, _span: &Span| {
        //                 tracing::error!("{}",error);
        //     })
        // )
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


    // let manager = EventManager::new();

    
    // manager.register_action(Events::SystemStartup,        
    //         Box::new(move | _tx:&Option<ContextData> | 
    //         {
    //             info!("I am here baby");
    //         }),
    //         None,None
    // );

    // manager.register_action(Events::SystemPoweroff, 
    //     Box::new(
    //         move | ctx:&Option<ContextData> | 
    //         {
    //             if let Some(map) = ctx
    //             {
    //                 if let Some(timestamp) = map.get(&ISOTimestamp)
    //                 {
    //                     error!("Bye Bye at {}",timestamp);
    //                     return;
    //                 }
    //             }

    //             error!("Bye Bye");
    //         }
    //     ),Some("0123-4567-89ab-cdef".to_string()),None
    // );

    // manager.register_action(
    //     Events::Timer,
    //         Box::new(move | _ctx:&Option<ContextData> | { debug!("Heatbeat")}) ,
    //     None, Some(vec![EventParameters::Timer(3)]));

    // manager.start();

    // thread::sleep(time::Duration::from_secs(5));

    // manager.trigger(Trigger::Event(Events::SystemStartup),None);

    // Touch(&"a.txt".to_string(), None).run();

    // thread::sleep(time::Duration::from_secs(7));

    // manager.trigger(Trigger::Event(Events::SystemPoweroff),None);

    // RM(&"a.txt".to_string(),false,false,None).run();

    // thread::sleep(time::Duration::from_secs(2));

    // manager.stop();

    // manager.join();
}
