use config::Config;
use std::fs;
use std::net::SocketAddrV4;
use std::error::Error;
use std::sync::{OnceLock,Mutex,Arc};
use tracing::{info,error,warn};


pub mod config;
pub mod api;
pub mod utils;

static BACKEND:OnceLock<Arc<Backend>> = OnceLock::new();
static NMS_CONFIG_FILE:&str = "nms.conf.json";

pub struct Quota
{
    pub quota:Option<u64>,
    pub used: Option<u64>
}

pub struct User
{
    pub username:String,
    pub visible_name:Option<String>,
    pub permissions: Vec<String>,
    pub quota:Option<Quota>,
    pub sudo: bool,
    pub admin:bool,
    pub first_login_token:Option<String>,
    pub home_dir: Option<Path>,
    pub uid:Option<u32>,
    pub gid:Option<u32>,
    pub notifications:u32,
}


pub struct Backend
{
    config:Mutex<Config>,
    users:Mutex<Vec<User>>
}

impl Backend
{
    fn new() -> Arc<Self>
    {
        let backend = Backend{
                config:Mutex::new(Config::default()),
                users:Mutex::new(vec![])
        };

        backend.reload_users();

        return Arc::new(backend);
    }

    fn reload_users(self:&Arc<Self>)
    {
        if let Ok(mut users) = self.users.lock()
        {
            users.clear();

            if let Ok(cfg) = self.config.lock()
            {
                for (uname, prop) in cfg
                {
                    //quota detection



                    // sudo detection
                    let mut sudo:bool = false;

                    if let Some(group_output) = Groups(uname,Some(&config)).run()
                    {
                        if group_output.status_code == 0
                        {
                            if let Some(_) = group_output.stdout.find(sudo_group())
                            {
                                sudo = true;
                            }
                        }
                    }

                    //first token

                    //get home - uid - gid

                    //return
                }
            }
        }
    }

    pub fn is_otp_configured(self:&Arc<Self>) -> bool
    {
        //TODO: fix this
        false
    }

    pub fn get_bind_addr(self:&Arc<Self>) -> SocketAddrV4
    {
        let cfg = self.config.lock().unwrap();

        SocketAddrV4::new(
            cfg.daemon.host,
            cfg.daemon.port
        )
    }

    pub fn read_config(self:&Arc<Self>) -> Result<(),Box<dyn Error + '_>>
    {
        let json = fs::read_to_string(NMS_CONFIG_FILE)?;

        let mut cfg = self.config.lock()?;

        *cfg = serde_json::from_str(&json)?;

        Ok(())
    }

    pub fn flush_config(self:&Arc<Self>) -> Result<(),Box<dyn Error + '_>>
    {
        let mut tmp_file = NMS_CONFIG_FILE.to_string();
        tmp_file.push('~');

        let result = fs::File::create(&tmp_file);

        if let Err(e) = result
        {
            error!("Unable to open configuration file: {e}");
            return Err(Box::new(e));
        }
        else 
        {
            let file = result.unwrap();
            let cfg = self.config.lock().unwrap();
            let result = serde_json::to_writer_pretty(file,&(*cfg));

            if let Err(e) = result
            {
                error!("Unable to save configuration file: {e}");
                return Err(Box::new(e));
            }

            match fs::rename(tmp_file, NMS_CONFIG_FILE)
            {
                Err(e) => {
                    error!("Unable to move configuration file: {e}");
                    return Err(Box::new(e));
                },
                _ => ()
            }

            Ok(())
        }
    }
}

pub fn get_backend() -> Arc<Backend>
{
    BACKEND.get_or_init(|| {
        //read configuration file
        let backend = Backend::new();

        {

            info!("NMS Backend started");

            if let Err(err) = backend.read_config()
            {
                error!("Unable to read configuration file:{err}");
                warn!("Creating a new configuration file with default values");
                match backend.flush_config()
                {
                    Ok(()) => info!("New configuration file created"),
                    Err(_) => std::process::exit(1)
                }
            }

            info!("NMS Backend initialised");        
        }

        backend
    }).clone()
}