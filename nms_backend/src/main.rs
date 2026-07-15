use core::time;
use std::thread;
use tracing::Level;
use tracing_subscriber::FmtSubscriber;

use crate::events::EventManager;


pub mod cmdl;
pub mod events;

// use crate::cmdl::{Executable,CmdConfig};
// use crate::cmdl::coreutils::{LS, Cat,CreateKey,RM, POSIXPermissions};

fn main() 
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

    let mut manager = EventManager::new();

    manager.start();

    thread::sleep(time::Duration::from_secs(12));

    manager.stop();

    manager.join();
}
