use core::time;
use std::collections::HashMap;
use std::sync::{Arc,mpsc};
use std::sync::atomic::{AtomicBool,Ordering};
use std::thread;
use tracing::{debug,info,warn};


type ContextData = HashMap<ContextVariables,String>;
type EventCallback = Box<dyn Fn(ContextData)+Send>;
pub enum Events
{
    SystemStartup(ContextData),
    SystemReboot(ContextData),
    SystemPoweroff(ContextData),
    SystemShutdown(ContextData),
    SystemSystemd(ContextData),
    SystemUpdates(ContextData),
    SystemUpgrade(ContextData),
    SystemNMSUpdates(ContextData),
    SystemNMSUpgrade(ContextData),
    Timer(ContextData),
    PoolMount(ContextData),
    PoolUnmont(ContextData),
    UserLoggedIn(ContextData),
    UserCreated(ContextData),
    UserDeleted(ContextData),
    AccessEnabled(ContextData),
    AccessDisabled(ContextData),
    VPNEnabled(ContextData),
    VPNDisabled(ContextData),
    FileCreated(ContextData),
    FileDeleted(ContextData),
    FileModified(ContextData),
    FileShared(ContextData),
}

pub enum ContextVariables
{
    TriggerUser,
    User,
    Group,
    Account,
    ISOTimestamp,
    Packages,
    Service,
    Path,
    Filename,
    IsDir,
    HomeOwner,
    Permissions,
    Token
}

impl std::fmt::Display for ContextVariables
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        match self
        {
            ContextVariables::TriggerUser => write!(f,"TRIGGER_USER"),
            ContextVariables::User => write!(f,"USER"),
            ContextVariables::Group => write!(f,"GROUP"),
            ContextVariables::Account => write!(f,"ACCOUNT"),
            ContextVariables::ISOTimestamp => write!(f,"ISO_TIMESTAMP"),
            ContextVariables::Packages => write!(f,"PACKAGES"),
            ContextVariables::Service => write!(f,"SERVICE"),
            ContextVariables::Path => write!(f,"PATH"),
            ContextVariables::Filename => write!(f,"FILENAME"),
            ContextVariables::IsDir => write!(f,"ISDIR"),
            ContextVariables::HomeOwner => write!(f,"HOME_OWNER"),
            ContextVariables::Permissions => write!(f,"PERMISSIONS"),
            ContextVariables::Token => write!(f,"TOKEN"),
        }
    }
}

pub enum EventAction
{
    Internal
    {
        callback:EventCallback
    },

    UserDefined
    {
        uuid:String,
        callback:EventCallback
    }
}

pub struct EventManager
{
    registered_actions:Arc<HashMap<Events,Vec<EventAction>>>,
    tx:Option<mpsc::Sender<Events>>,
    rx:Option<mpsc::Receiver<Events>>,
    running_state:Arc<AtomicBool>,
    thread:Option<thread::JoinHandle<()>>
}

impl EventManager
{
    pub fn new() -> EventManager
    {
        EventManager
        { 
            registered_actions: Arc::new(HashMap::new()),
            tx: None, 
            rx: None,
            running_state: Arc::new(AtomicBool::new(false)),
            thread: None
        }
    }

    pub fn start(&mut self)
    {
        let (tx,rx) = mpsc::channel::<Events>();

        self.tx = Some(tx);
        self.rx = Some(rx);

        self.running_state.store(true, Ordering::Relaxed);

                
        let thread_running_state = Arc::clone(&self.running_state);

        let t = thread::Builder::new()
            .name("Event Manager".to_string())
            .spawn(
                move || 
                {
                    info!("Event Manager Started");
                    while thread_running_state.load(Ordering::Relaxed)
                    {
                        thread::sleep(time::Duration::from_secs(5));
                        debug!("Looping");
                    }
                    warn!("Event Manager Stopped");
                }
            ).expect("Unable to start event manager.");

        self.thread = Some(t);

    }

    pub fn stop(&mut self)
    {
        self.running_state.store(false,Ordering::Relaxed);
        
        self.tx.take();
        self.rx.take();
    }

    pub fn join(&mut self)
    {
        if let Some(th) = self.thread.take()
        {
            th.join();
        }
    }
}