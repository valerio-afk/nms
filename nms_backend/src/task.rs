use std::sync::{Arc,atomic::{AtomicBool,Ordering}};
use std::future::Future;
use std::ops::Deref;
use std::pin::Pin;
use async_trait::async_trait;
use tokio::task::JoinHandle;
use tokio::sync::Mutex;
use tracing::{debug};


pub type TaskFuture = Pin<Box<dyn Future<Output = ()> + Send>>;
pub type Runner<S> = Box<dyn  Fn(&S) -> TaskFuture + Send + Sync>;

#[async_trait]
pub trait TaskWrapper
{
    async fn start(&self);
    async fn stop(&self);
    async fn join(&self);
    fn is_running(&self) -> bool;
}



pub struct WrappedTaskInternal
{
    running_state: Arc<AtomicBool>,
    name:Option<String>,
    run: Runner<WrappedTask>,
    handle: Mutex<Option<JoinHandle<()>>>
}


impl WrappedTaskInternal
{
    fn new(callback:Runner<WrappedTask>,name:Option<String>) -> WrappedTaskInternal
    {
        WrappedTaskInternal
        {
            running_state: Arc::new(AtomicBool::new(false)),
            handle: Mutex::new(None),
            name: name,
            run:  callback
        }
    }
}

#[derive(Clone)]
pub struct WrappedTask
{
    internal:Arc<WrappedTaskInternal>,
}

impl WrappedTask
{
    
    pub async fn new(callback:Runner<Self>,name:Option<String>) -> Self
    {
        WrappedTask
        {
            internal: Arc::new(WrappedTaskInternal::new(callback, name))
        }
    }
}

impl Deref for WrappedTask
{
    type Target = WrappedTaskInternal;
    fn deref(&self) -> &Self::Target
    {
        &self.internal
    }
}

#[async_trait]
impl TaskWrapper for WrappedTask
{
    async fn start(&self)
    {
        self.running_state.store(true, Ordering::Relaxed);

        let this = self.clone();

        let handle = tokio::spawn(
            async move { (this.run)(&this).await }
        );

        let task_name = match &self.name
        {
            Some(n) => n.clone(),
            None => "Anonymous task".to_string()
        };

        let mut h = self.handle.lock().await;
        *h= Some(handle);

        let debug_str = format!("Task {} started",task_name);
        debug!("{debug_str}");

    }

    async fn stop(&self)
    {
        self.running_state.store(false,Ordering::Relaxed);
    }

    async fn join(&self)
    {
        let mut h = self.handle.lock().await;
        if h.is_some()
        {
            let _ = h.as_mut().take().unwrap().await;
        }
    }

    fn is_running(&self) -> bool
    {
        self.running_state.load(Ordering::Relaxed)
    }
}