use core::time;
use std::thread;
use tracing::{Level,info,error,debug};
use tracing_subscriber::FmtSubscriber;

use crate::events::{ContextData, ContextVariables::ISOTimestamp, EventManager, EventParameters, Events, Trigger};
use thread_wrapper::ThreadWrapper;

pub mod cmdl;
pub mod events;
pub mod thread_wrapper;

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


fn main() 
{
    logger_init();

    let manager = EventManager::new();

    
    manager.register_action(Events::SystemStartup,        
            Box::new(move | _ctx:&Option<ContextData> | 
            {
                info!("I am here baby");
            }),
            None,None
    );

    manager.register_action(Events::SystemPoweroff, 
        Box::new(
            move | ctx:&Option<ContextData> | 
            {
                if let Some(map) = ctx
                {
                    if let Some(timestamp) = map.get(&ISOTimestamp)
                    {
                        error!("Bye Bye at {}",timestamp);
                        return;
                    }
                }

                error!("Bye Bye");
            }
        ),Some("0123-4567-89ab-cdef".to_string()),None
    );

    manager.register_action(
        Events::Timer,
            Box::new(move | _ctx:&Option<ContextData> | { debug!("Heatbeat")}) ,
        None, Some(vec![EventParameters::Timer(3)]));

    manager.start();

    thread::sleep(time::Duration::from_secs(5));

    manager.trigger(Trigger::Event(Events::SystemStartup),None);

    thread::sleep(time::Duration::from_secs(7));

    manager.trigger(Trigger::Event(Events::SystemPoweroff),None);

    thread::sleep(time::Duration::from_secs(2));

    manager.stop();

    manager.join();
}
