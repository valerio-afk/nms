use std::collections::HashMap;
use std::sync::{atomic::{AtomicBool, Ordering}, Arc};
use std::future::Future;
use std::ops::Deref;
use std::pin::Pin;
use anyhow::Error;
use async_trait::async_trait;
use tokio::task::{JoinError, JoinHandle};
use tokio::sync::{Mutex, RwLock, Notify};
use tracing::{debug};
use uuid::Uuid;

pub type TaskFuture = Pin<Box<dyn Future<Output = ()> + Send>>;
pub type Runner<S> = Box<dyn  Fn(&S) -> TaskFuture + Send + Sync>;

pub type BackgroundTaskResult<R,E> = Result<R,E>;
pub type BackgroundTaskFuture<R,E> = Pin<Box<dyn Future<Output = BackgroundTaskResult<R,E>> + Send + Sync>>;
pub type BackgroundRunner<S,R,E> = Box<dyn  Fn(&S) -> BackgroundTaskFuture<R,E> + Send + Sync>;

#[async_trait]
pub trait Task: Send + Sync
{
    type Output;
    async fn start(&self);
    async fn stop(&self);
    async fn join(&self) -> Result<Self::Output,Error>;
    async fn is_running(&self) -> bool;
}



pub struct SimpleTaskInternal
{
    running_state: Arc<AtomicBool>,
    name:Option<String>,
    run: Runner<SimpleTask>,
    handle: Mutex<Option<JoinHandle<()>>>
}


impl SimpleTaskInternal
{
    fn new(callback:Runner<SimpleTask>, name:Option<String>) -> SimpleTaskInternal
    {
        SimpleTaskInternal
        {
            running_state: Arc::new(AtomicBool::new(false)),
            handle: Mutex::new(None),
            name: name,
            run:  callback
        }
    }
}

#[derive(Clone)]
pub struct SimpleTask
{
    internal:Arc<SimpleTaskInternal>,
}

impl SimpleTask
{
    
    pub async fn new(callback:Runner<Self>,name:Option<String>) -> Self
    {
        SimpleTask
        {
            internal: Arc::new(SimpleTaskInternal::new(callback, name))
        }
    }
}

impl Deref for SimpleTask
{
    type Target = SimpleTaskInternal;
    fn deref(&self) -> &Self::Target
    {
        &self.internal
    }
}

#[async_trait]
impl Task for SimpleTask
{
    type Output = ();
    async fn start(&self)
    {

        let this = self.clone();

        let handle = tokio::spawn(

            async move {
                this.running_state.store(true, Ordering::Relaxed);
                (this.run)(&this).await;
                this.running_state.store(false, Ordering::Relaxed);
            }
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

    async fn join(&self) -> Result<(),Error>
    {
        let mut h = self.handle.lock().await;
        if h.is_some()
        {
            let x = h.as_mut().take().unwrap().await;
            return match x
            {
                Ok(_) => Ok(()),
                Err(e) => Err(Error::new(e))
            }
        }

        Ok(())
    }

    async fn is_running(&self) -> bool
    {
        self.running_state.load(Ordering::Relaxed)
    }
}

pub struct BackgroundTaskInner<S,R>
{
    running_state: AtomicBool,
    name:Option<String>,
    run: BackgroundRunner<S,R,Error>,
    eta:Option<u32>,
    progress:Option<f32>,
    handle: RwLock<Option<JoinHandle<BackgroundTaskResult<R,Error>>>>
}

impl<S,R> BackgroundTaskInner<S,R>
{
    pub fn get_progress(&self) -> Option<f32> { self.progress }
    pub fn get_eta(&self) -> Option<u32> { self.eta }
    pub fn get_name(&self) -> Option<&String> { self.name.as_ref() }
}

#[derive(Clone)]
pub struct BackgroundTask<R>
{
    inner:Arc<BackgroundTaskInner<Self,R>>,
}

impl<R> BackgroundTask<R>
{
    pub fn new(callback:BackgroundRunner<Self,R,Error>,name:Option<String>) -> BackgroundTask<R>
    {
        BackgroundTask{
            inner: Arc::new(
                BackgroundTaskInner {
                    running_state: AtomicBool::new(false),
                    name,
                    run: callback,
                    eta: None,
                    progress: None,
                    handle: RwLock::new(None)
                }
            )
        }
    }
}

impl<R> Deref for BackgroundTask<R>
{
    type Target = BackgroundTaskInner<Self,R>;
    fn deref(&self) -> &Self::Target
    {
        &self.inner
    }
}

#[async_trait]
impl<R> Task for BackgroundTask<R>
where
    R: Clone + Send + Sync +'static
{
    type Output = Option<R>;
    async fn start(&self)
    {
        let this = BackgroundTask{
            inner: self.inner.clone(),
        };


        let r:JoinHandle<_> = tokio::spawn(async move
            {
                this.running_state.store(true, Ordering::Relaxed);
                let result = (this.run)(&this).await;

                return result;
            });


        let mut h = self.handle.write().await;
        *h = Some(r);
    }

    async fn stop(&self)
    {
        self.inner.running_state.store(false, Ordering::Relaxed);
    }

    async fn is_running(&self) -> bool
    {
        let h = self.handle.read().await;

        if let Some(handle) = &*h
        {
            let finished = handle.is_finished();
            
            if finished
            {
                self.stop().await;
            }

            return !finished;
        }

        false
    }

    async fn join(&self) -> Result<Option<R>,Error>
    {
        let mut h =self.inner.handle.write().await;
        if h.is_some()
        {
            let r = h.take().unwrap().await;
            return match r
            {
                Ok(r) => match r {
                    Ok(r) => Ok(Some(r)),
                    Err(e) => Err(e)
                }
                Err(e) => Err(Error::new(e))
            }
        }

        Ok(None)
    }
}

pub struct BackgroundTaskManager<R>
{
    tasks: RwLock<HashMap<String,Arc<BackgroundTask<R>>>>,
    handle: RwLock<Option<JoinHandle<()>>>,
    notify: Notify
}

impl<R> BackgroundTaskManager<R>
where
    R: Clone + Send + Sync +'static
{
    pub fn new() -> Arc<BackgroundTaskManager<R>>
    {
        Arc::new(BackgroundTaskManager
        {
            tasks: RwLock::new(HashMap::new()),
            handle: RwLock::new(None),
            notify: Notify::new()
        })
    }


    pub async fn add_task(&self, task:Arc<BackgroundTask<R>>) -> Uuid
    {
        let uuid = Uuid::new_v4();
        let mut tasks = self.tasks.write().await;
        tasks.insert(uuid.to_string(),Arc::clone(&task));
        task.start().await;
        uuid
    }

    async fn _remove_task(self:&Arc<Self>, uuid:&String) -> Option<Arc<BackgroundTask<R>>>
    {
        let mut tasks = self.tasks.write().await;
        if let Some(task) = tasks.remove(uuid)
        {
            task.stop().await;
            return Some(task);
        }

        None
    }

    pub async fn remove_task(self:&Arc<Self>, uuid:Uuid) -> Option<Arc<BackgroundTask<R>>>
    {
        let task = self._remove_task(&uuid.to_string()).await;
        task
    }

    pub async fn stop_all_tasks(self:&Arc<Self>) -> Result<(),JoinError>
    {
        let tasks = self.tasks.read().await;
        let task_ids = tasks.keys().cloned().collect::<Vec<_>>();
        drop(tasks);

        for task_id in task_ids
        {
            self._remove_task(&task_id).await;
        }

        if let Some(handle) = self.handle.write().await.take()
        {
            handle.await?;
        }

        Ok(())
    }

    pub async fn get_task_by_id(&self,id:&str)-> Option<Arc<BackgroundTask<R>>>
    {
        let tasks = self.tasks.read().await;

        if let Some(t) = tasks.get(id)
        {
            return Some(Arc::clone(t));
        }
        None
    }
}