use uuid::Uuid;
use std::collections::HashMap;
use std::io::{BufRead, BufReader};
use std::os::fd::AsFd;
use std::sync::{Arc,mpsc,Mutex};
use std::sync::atomic::{AtomicBool,Ordering};
use std::thread;
use std::time::Duration;
use std::path::Path;
use tracing::{debug,info,warn,error};
use chrono::Local;
use nix::poll::{poll, PollFd, PollFlags};
use serde::{Serialize,Deserialize};
 
use crate::thread_wrapper::{ThreadWrapper, WrappedThread};
use crate::cmdl::{CmdConfig, Executable};
use crate::cmdl::coreutils::{Stat,StatFormat};
use crate::cmdl::notify::{INotifyEvents,INotifyWait};


pub mod actions;

pub type ContextData = HashMap<ContextVariables,String>;
pub type EventCallback = Arc<dyn Fn(&Option<ContextData>)+Send+Sync>;
pub type EventData = (Trigger,Option<ContextData>);

#[derive(Eq, Hash, PartialEq, Clone, Debug, Serialize, Deserialize)]
pub enum Events
{
    SystemStartup,
    SystemReboot,
    SystemPoweroff,
    SystemShutdown,
    SystemSystemd,
    SystemUpdates,
    SystemUpgrade,
    SystemNMSUpdates,
    SystemNMSUpgrade,
    Timer,
    PoolMount,
    PoolUnmont,
    UserLoggedIn,
    UserCreated,
    UserModified,
    UserDeleted,
    AccessEnabled,
    AccessDisabled,
    VPNEnabled,
    VPNDisabled,
    FileCreated,
    FileDeleted,
    FileModified,
    FileShared
}

#[derive(Clone)]
pub enum EventParameters
{
    Timer(u64),
    None // just to silence the compiler with irrifutable bla bla bla
}

impl std::fmt::Display for Events
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        match self
        {
            Events::SystemStartup => write!(f,"SystemStartup"),
            Events::SystemReboot => write!(f,"SystemReboot"),
            Events::SystemPoweroff => write!(f,"SystemPoweroff"),
            Events::SystemShutdown => write!(f,"SystemShutdown"),
            Events::SystemSystemd => write!(f,"SystemSystemd"),
            Events::SystemUpdates => write!(f,"SystemUpdates"),
            Events::SystemUpgrade => write!(f,"SystemUpgrade"),
            Events::SystemNMSUpdates => write!(f,"SystemNMSUpdates"),
            Events::SystemNMSUpgrade => write!(f,"SystemNMSUpgrade"),
            Events::Timer => write!(f,"Timer"),
            Events::PoolMount => write!(f,"PoolMount"),
            Events::PoolUnmont => write!(f,"PoolUnmont"),
            Events::UserLoggedIn => write!(f,"UserLoggedIn"),
            Events::UserCreated => write!(f,"UserCreated"),
            Events::UserModified => write!(f,"UserModified"),
            Events::UserDeleted => write!(f,"UserDeleted"),
            Events::AccessEnabled => write!(f,"AccessEnabled"),
            Events::AccessDisabled => write!(f,"AccessDisabled"),
            Events::VPNEnabled => write!(f,"VPNEnabled"),
            Events::VPNDisabled => write!(f,"VPNDisabled"),
            Events::FileCreated => write!(f,"FileCreated"),
            Events::FileDeleted => write!(f,"FileDeleted"),
            Events::FileModified => write!(f,"FileModified"),
            Events::FileShared => write!(f,"FileShared"),
        }
    }
}

impl Events
{
    pub fn get_context_variables(&self) -> Vec<ContextVariables>
    {
        let mut ctx_var : Vec<ContextVariables> = vec![ContextVariables::ISOTimestamp];
        let inotfy_ctx = vec![
            ContextVariables::IsDir,
            ContextVariables::Path,
            ContextVariables::Filename,
            ContextVariables::HomeOwner
        ];
        
        match self
        {
            Events::SystemUpdates => ctx_var.push(ContextVariables::Packages),
            Events::SystemUpgrade => ctx_var.push(ContextVariables::Packages),
            Events::UserLoggedIn => ctx_var.push(ContextVariables::TriggerUser),
            Events::UserCreated => ctx_var.extend(vec![ContextVariables::TriggerUser,ContextVariables::Account]),
            Events::UserDeleted => ctx_var.extend(vec![ContextVariables::TriggerUser,ContextVariables::Account]),
            Events::AccessEnabled => ctx_var.extend(vec![ContextVariables::TriggerUser,ContextVariables::Account,ContextVariables::Service]),
            Events::AccessDisabled => ctx_var.extend(vec![ContextVariables::TriggerUser,ContextVariables::Account,ContextVariables::Service]),
            Events::VPNEnabled => ctx_var.push(ContextVariables::TriggerUser),
            Events::VPNDisabled => ctx_var.push(ContextVariables::TriggerUser),
            Events::FileShared  => ctx_var.extend(vec![ContextVariables::TriggerUser,ContextVariables::Account,ContextVariables::Token]),
            Events::FileCreated => ctx_var.extend(inotfy_ctx),
            Events::FileModified => ctx_var.extend(inotfy_ctx),
            Events::FileDeleted => ctx_var.extend(inotfy_ctx),
            _ => ()
        }

        return ctx_var;
    }
}

#[derive(Eq, Hash, PartialEq)]
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

pub struct ContextBuilder
{
    map:HashMap<ContextVariables,String>
}

impl ContextBuilder
{
    pub fn new() -> Self
    {
        ContextBuilder { map: HashMap::new() }
    }

    pub fn from(var:ContextVariables, value:String) -> Self
    {
        ContextBuilder::new().push(var, value)
    }

    pub fn push(mut self, var:ContextVariables, value:String) -> Self
    {
        self.map.insert(var, value);
        return self;
    }

    pub fn finish(self) -> Option<HashMap<ContextVariables,String>>
    {
        if self.map.is_empty() { None }
        else {Some(self.map)}
    }
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

pub struct EventAction
{
    uuid:String,
    callback:EventCallback
}


pub struct EventManager
{
    registered_actions:Arc<Mutex<HashMap<Events,Vec<EventAction>>>>,
    tx:Mutex<Option<mpsc::Sender<EventData>>>,
    running_state:Arc<AtomicBool>,
    main_thread:Mutex<Option<thread::JoinHandle<()>>>,
    threads:Mutex<HashMap<String,Arc<WrappedThread>>>
}

pub enum Trigger
{
    Event(Events),
    Action(String)
}

impl EventManager
{
    fn start_inotify_thread(self: &Arc<Self>,path:&str)
    {
        let config: CmdConfig = CmdConfig::new(
            true,
            true,
            None,
            None
        );

        let manager = Arc::clone(&self);
        let thread_name = "INotifyThread".to_string();
        let thread_path = path.to_string();


        let th = WrappedThread::new(
            Box::new(
                move |this:&Arc<WrappedThread>|
                {
                    let cmd = INotifyWait(
                        &thread_path, 
                        true, 
                        true, 
                        vec![INotifyEvents::Create,INotifyEvents::Delete,INotifyEvents::Modify], 
                        Some(&"%e%0%w%0%f".to_string()), 
                        Some(&config)
                    );

                    let result = cmd.spawn();
                    
                    if let Err(e) = result
                    {
                        error!("Unable to start inotifywait: {e}");
                    }
                    else 
                    {  
                        let mut child = result.unwrap();  
                        let stdout = child.stdout.take().unwrap();

                        let mut reader = BufReader::new(stdout);    

                        info!("Started");

                        while this.is_running()
                        {
                            {
                                let fd = reader.get_ref().as_fd();
                                let mut fds = [PollFd::new(fd,PollFlags::POLLIN)];
                                let ready = poll(&mut fds,3000u16);

                                

                                match ready
                                {
                                    Ok(num) => 
                                    {
                                        if num == 0 { continue; }
                                    }
                                    Err(_) => {continue;}
                                }

                            }
                            

                            if let Ok(Some(status)) = child.try_wait()
                            {
                                error!("inotifywait ended unexpectedly: {status}");
                                break;
                            }


                            let mut line = String::new();
                            let n = reader.read_line(&mut line);

                            match n
                            {
                                Ok(bytes) => 
                                {
                                    if bytes == 0 
                                    {
                                        thread::sleep(std::time::Duration::from_secs(2));
                                        error!("Bytes received: {bytes}"); continue; 
                                    }
                                }
                                Err(err) =>
                                {
                                    error!("Error while reading the stdout from inotifywait: {err}");
                                    break;
                                }
                            }


                            let tokens:Vec<&str> = line.split("\0").collect();

                            if tokens.len() == 3
                            {
                                let event = tokens[0];
                                let path = tokens[1];
                                let name = tokens[2];

                                let is_dir =  if let Some(_) = event.find("ISDIR") { "1" } else { "0" };
                            
                                let event_to_trigger:Option<INotifyEvents> = {
                                    if let Some(_) = event.find("CREATE") { Some(INotifyEvents::Create) }
                                    else if let Some(_) = event.find("MODIFY") { Some(INotifyEvents::Modify) }
                                    else if let Some(_) = event.find("DELETE") { Some(INotifyEvents::Delete) }
                                    else {None}
                                };

                                if let Some(e) = event_to_trigger
                                {
                                    let mut ctx: HashMap<ContextVariables,String> = HashMap::new();

                                    ctx.insert(ContextVariables::IsDir, is_dir.to_string());
                                    ctx.insert(ContextVariables::Path, path.to_string());
                                    ctx.insert(ContextVariables::Filename, name.to_string());

                                    //TODO: implement line thread.py:222 with call to get_home_owner                            
                                    //ctx.insert(ContextVariables::HomeOwner, "");

                                    let perform_stat = 
                                    {
                                        match e
                                        {
                                            INotifyEvents::Delete => false,
                                            _ => true
                                        }
                                    };

                                    if perform_stat
                                    {
                                        let pth = Path::new(path).join(name);
                                        let stat = Stat(&pth.to_string_lossy().to_string(),Some(
                                                vec![
                                                    StatFormat::PermissionsOctal,
                                                    StatFormat::Filler(" "),
                                                    StatFormat::User,
                                                    StatFormat::Filler(" "),
                                                    StatFormat::GroupName,
                                                ]
                                            ),
                                            None
                                        );

                                        let result = stat.run();

                                        let mut user = String::new();
                                        let mut group = String::new();
                                        let mut permissions = String::new();

                                        if let Some(output) = result
                                        {
                                            if output.status_code == 0
                                            {
                                                let tokens:Vec<&str> = output.stdout.split(" ").collect();

                                                if tokens.len()==3
                                                {
                                                    user = tokens[0].to_string();
                                                    group = tokens[1].to_string();
                                                    permissions = tokens[2].to_string();
                                                }
                                            }
                                        }

                                        ctx.insert(ContextVariables::User,user);
                                        ctx.insert(ContextVariables::Group,group);
                                        ctx.insert(ContextVariables::Permissions,permissions);
                                    }    

                                    let event_trigger:Events = {
                                        match e
                                        {
                                            INotifyEvents::Create => Events::FileCreated,
                                            INotifyEvents::Modify => Events::FileModified,
                                            INotifyEvents::Delete => Events::FileDeleted,
                                        }
                                    };                   

                                    //TODO: introduce delayed actions when uploading a file
                                    manager.trigger(
                                        Trigger::Event(event_trigger),
                                        Some(ctx)
                                    );
                                }
                                
                            }


                        }
                    }
                    warn!("Ended");
                }
            ),
            Some(thread_name.clone())
        );

        th.start();

        let mut map = self.threads.lock().unwrap();
        map.insert(thread_name, th);
    }
}


impl ThreadWrapper for EventManager
{
    fn start(self: &Arc<Self>)
    {
        let (tx,rx) = mpsc::channel::<EventData>();

        *self.tx.lock().unwrap() = Some(tx);

        self.running_state.store(true, Ordering::Relaxed);

        self.start_inotify_thread("/nms/nms_backend");
                
        let this = Arc::clone(&self);

        let t = thread::Builder::new()
            .name("Event Manager".to_string())
            .spawn(
                move || 
                {
                    info!("Event Manager Started");

                    while this.running_state.load(Ordering::Relaxed)
                    {
                        let event_data = rx.recv_timeout(Duration::from_secs(1));

                        if let Ok((trigger,ctx)) = event_data
                        {
                            let mut uuids:Vec<&str> = Vec::new();

                            

                            let map = this.registered_actions.lock().unwrap();

                            if let Trigger::Event(ev) = trigger
                            {
                                debug!("Received {ev}");
                                if let Some(lst) = map.get(&ev)
                                {
                                    for action in lst
                                    {
                                        uuids.push(&action.uuid);
                                        (action.callback)(&ctx);
                                    }
                                }

                                if uuids.len()==0
                                {
                                    debug!("No action found for {ev}.");
                                }
                                else 
                                {
                                        debug!("{ev} dispatched to: {}.",uuids.join(", "));
                                }
                            }
                            else if let Trigger::Action(uuid) = &trigger
                            {
                                debug!("Received trigger for {uuid}");

                                for (_,lst) in map.iter()
                                {
                                    for action in lst
                                    {
                                        
                                        if action.uuid == *uuid
                                        {
                                            (action.callback)(&ctx);
                                            debug!("Event dispatched for {uuid}");
                                            break;
                                        }
                                    }
                                }
                            }

                        }
                    }
                    warn!("Event Manager Stopped");
                }
            ).expect("Unable to start event manager.");

        *self.main_thread.lock().unwrap() = Some(t);

    }

    fn stop(self:&Arc<Self>)
    {
        self.running_state.store(false,Ordering::Relaxed);
        
        self.tx.lock().unwrap().take();

        for (_,t) in self.threads.lock().unwrap().iter()
        {
            t.stop();
        }
        
    }

    fn join(self:&Arc<Self>)
    {
        if let Some(th) = self.main_thread.lock().unwrap().take()
        {
            let _ = th.join();
        }

        for (_,t) in self.threads.lock().unwrap().iter()
        {
            t.join();
        }
    }

    fn is_running(self:&Arc<Self>) -> bool 
    {
        self.running_state.load(Ordering::Relaxed)
    }

}

impl EventManager
{
    pub fn new() -> Arc<EventManager>
    {
        Arc::new(EventManager
        { 
            registered_actions: Arc::new(Mutex::new(HashMap::new())),
            tx: Mutex::new(None),
            running_state: Arc::new(AtomicBool::new(false)),
            main_thread: Mutex::new(None),
            threads: Mutex::new(HashMap::new())
        })
    }

    

    pub fn trigger(self:&Arc<Self>, trigger:Trigger,ctx:Option<HashMap<ContextVariables,String>>)
    {

        if let Some(tx) = self.tx.lock().unwrap().as_ref()
        {
            let mut map:HashMap<ContextVariables,String>;
            if let Some(m) = ctx
            {
                map = m;
            }
            else 
            {
                map = HashMap::new();
            }

            map.entry(ContextVariables::ISOTimestamp).or_insert(Local::now().to_rfc3339());
            let _ = tx.send((trigger,Some(map)));
        }
    }

    pub fn register_action(
        self:&Arc<Self>,
        event:&Events,
        action:EventCallback,
        uuid:Option<String>,
        event_params:Option<Vec<EventParameters>>
    )
    {
        let mut map = self.registered_actions.lock().unwrap();
        //let mut map = lock.unwrap();
        let mut v = map.get_mut(event);

        let action_uuid:String = {

            match uuid
            {
                None => Uuid::new_v4().to_string(),
                Some(x) => x
            }
        };

        let new_action = EventAction{
            uuid:action_uuid.clone(),
            callback: action
        };

        if let Some(lst) = &mut v
        {
            lst.push(new_action);
        }
        else 
        {
            let lst:Vec<EventAction> = vec![new_action];
            map.insert(event.clone(), lst);
        }

        if event == &Events::Timer
        {
            let mut secs:u64 = 0;

            if let Some(args) = event_params
            {
                for a in args
                {
                    if let EventParameters::Timer(s) = a
                    {
                        secs = s;
                    }
                }
            }

            if secs == 0
            {
                panic!("You must specify an amount of seconds >0 as an event parameter for Timer");
            }

            let mngt = Arc::clone(&self);
            let thread_uuid = action_uuid.clone();

            let timing_thread = WrappedThread::new(
                Box::new(move |this:&Arc<WrappedThread>| {
                    while this.is_running() 
                    {
                        thread::sleep(Duration::from_secs(secs));
                        mngt.trigger(
                            Trigger::Action(thread_uuid.clone()),
                            None
                        );
                    }
                }),
                Some(action_uuid.clone())
            );           

            timing_thread.start();
            self.threads.lock().unwrap().insert(action_uuid.clone(), timing_thread);

        }
                    
        debug!("Add a new event callback action {} for the event {}",action_uuid, event.to_string());
    }

    pub fn register_multiple_events
    (
        self:&Arc<Self>,
        events:&[&Events],
        action:EventCallback,
        event_params:Option<Vec<EventParameters>>
    )
    {
        for e in events
        {
            self.register_action(e, Arc::clone(&action), None, event_params.clone());
        }
    }
}

