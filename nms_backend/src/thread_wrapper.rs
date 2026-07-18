use std::sync::{Mutex,Arc,atomic::{AtomicBool,Ordering}};
use std::thread;
use tracing::{debug};

type Runner<T> = dyn Fn(&Arc<T>)->() + Send + Sync;

#[allow(unused_macros)]
macro_rules! lock {
    ($m:expr) => {{
        tracing::debug!(
            "Locking {} at {}:{}",
            stringify!($m),
            file!(),
            line!()
        );
        let guard = $m.lock().unwrap();
        tracing::debug!(
            "Locked {} at {}:{}",
            stringify!($m),
            file!(),
            line!()
        );
        guard
    }};
}

pub trait ThreadWrapper
{
    fn start(self:&Arc<Self>);
    fn stop(self:&Arc<Self>);
    fn join(self:&Arc<Self>);
    fn is_running(self:&Arc<Self>) -> bool;
}

pub struct WrappedThread
{
    running_state:Arc<AtomicBool>,
    thread:Mutex<Option<thread::JoinHandle<()>>>,
    name:Option<String>,
    run:Box<Runner<Self>>
}

impl WrappedThread
{
    
    pub fn new(callback:Box<Runner<Self>>,name:Option<String>) -> Arc<Self>
    {
        Arc::new(
            WrappedThread { 
                running_state: Arc::new(AtomicBool::new(false)), 
                thread: Mutex::new(None), 
                name: name,
                run:  callback
            }
        )
    }
}

impl ThreadWrapper for WrappedThread
{
    fn start(self:&Arc<Self>) 
    {
        self.running_state.store(true, Ordering::Relaxed);

        let mut th = thread::Builder::new();

        if let Some(n) = &self.name
        {
            th = th.name(n.clone());
        }

        let this = Arc::clone(&self);

        let thread_name = {
                match &self.name
                {
                    Some(n) => n,
                    None => "anonymous"
                }
            };

        let j = th
            .spawn(move|| { (this.run)(&this); } )
            .expect(&format!("Unable to start thread `{}`.",thread_name));

        *self.thread.lock().unwrap() = Some(j);

        let debug_str = format!("Thread {} started",thread_name);
        debug!("{debug_str}");

    }

    fn stop(self:&Arc<Self>)
    {
        self.running_state.store(false,Ordering::Relaxed);
        
    }

    fn join(self:&Arc<Self>)
    {
        if let Some(th) = self.thread.lock().unwrap().take()
        {
            let _ = th.join();
        }
    }

    fn is_running(self:&Arc<Self>) -> bool 
    {
        self.running_state.load(Ordering::Relaxed)
    }
}