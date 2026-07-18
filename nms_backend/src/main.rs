use tracing::{Level,error,debug};
use tracing_subscriber::FmtSubscriber;
use backend::get_backend;
use backend::utils::detect_distro_family;
use backend::api::get_api;
use std::sync::{Arc};
use axum::{Router};



//use {cmdl::coreutils::{Touch, RM}, events::{ContextData, ContextVariables::ISOTimestamp, EventManager, EventParameters, Events, Trigger}};
//use cmdl::Executable;
//use thread_wrapper::ThreadWrapper;

pub mod cmdl;
pub mod events;
pub mod thread_wrapper;
pub mod backend;


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

    let backend = get_backend();

    let app = Router::new()
        .merge(get_api())
        .with_state(Arc::clone(&backend));

    debug!("OS Family detected: {}",detect_distro_family());
        


    let addr = backend.get_bind_addr();

    

    let listener = tokio::net::TcpListener::bind(
        addr.to_string()
    ).await;

    match listener
    {
        Ok(t) => axum::serve(t,app).await.unwrap(),        
        Err(e) => error!("Unable to serve backend: {}",e),
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
