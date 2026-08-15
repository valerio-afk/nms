use std::collections::HashMap;
use std::sync::Arc;
use async_trait::async_trait;
use crate::cmdl::{CmdConfig, CommandLine, Executable};
use reqwest::{Client, Method, StatusCode};
use std::pin::Pin;
use serde_json::Value;

#[async_trait]
pub trait DDNSService: Send + Sync + 'static
{
    async fn update(&self) -> Result<(),anyhow::Error>;
}

pub type UpdateCallback<T> = Arc<dyn for<'a> Fn(&'a T) -> Pin<Box<dyn Future<Output = bool> + Send + 'a>> + Send + Sync + 'static>;

pub struct CommandBasedDDNSService
{
    command: CommandLine,
    callback: Option<UpdateCallback<String>>,
}

#[async_trait]
impl DDNSService for CommandBasedDDNSService
{
    async fn update(&self) -> Result<(),anyhow::Error>
    {
        let output = self
            .command
            .clone()
            .run()
            .await
            .map_err(|e| anyhow::anyhow!(e.to_string()))?
            .ok_or_else(|| anyhow::anyhow!("DDNS command could not be executed"))?
            .is_success()
            .map_err(|e| anyhow::anyhow!(e.to_string()))?;

        let combined_streams = format!("{}\n{}",output.stdout, output.stderr);

        if let Some(cb) = &self.callback
        {
            if !cb(&combined_streams).await
            {
                return Err(anyhow::anyhow!(combined_streams))
            }
        }


        Ok(())
    }
}

impl CommandBasedDDNSService
{
    pub fn new(cmd:CommandLine) -> Self
    {
        CommandBasedDDNSService{
            command: cmd,
            callback: None,
        }
    }

    pub fn set_callback(&mut self, cb:UpdateCallback<String>)
    {
        self.callback = Some(cb);
    }

}


pub struct AsyncFriendlyResponse
{
    pub status_code: StatusCode,
    pub body: Option<String>,
}
pub struct TokenBasedDDNSService
{
    url: String,
    method: Method,
    params: HashMap<String, String>,
    callback:Option<UpdateCallback<AsyncFriendlyResponse>>,
}

impl TokenBasedDDNSService
{
    pub fn new(url: String, method: Method, params: HashMap<String, String>) -> Self
    {
        TokenBasedDDNSService
        {
            url,
            method,
            params,
            callback: None,
        }
    }

    pub fn from_url(url:String) -> Self
    {
        TokenBasedDDNSService::new(url, Method::GET, HashMap::new())
    }

    pub fn push_param(mut self, key:String, value:String) -> Self
    {
        self.params.insert(key, value);
        self
    }

    pub fn set_callback(&mut self, cb:UpdateCallback<AsyncFriendlyResponse>)
    {
        self.callback = Some(cb);
    }
}

#[async_trait]
impl DDNSService for TokenBasedDDNSService
{
    async fn update(&self) -> Result<(),anyhow::Error>
    {
        let mut client = Client::new().request(self.method.clone(), self.url.as_str());

        if self.params.len() > 0
        {
            let p = self.params.iter().collect::<Vec<(&String,&String)>>();
            client = client.query(p.as_slice());
        }

        let response = client.send().await?;

        if let Some(cb) = &self.callback
        {
            let resp = AsyncFriendlyResponse{
                status_code: response.status(),
                body: match response.text().await
                {
                    Ok(t) => Some(t),
                    Err(_) => None
                }
            };

            if !cb(&resp).await
            {
                return Err(anyhow::anyhow!(resp.body.unwrap_or(String::new())));
            }
        }

        Ok(())
    }
}


pub fn NoIP (username: String, password: String) -> CommandBasedDDNSService
{
    let mut svc = CommandBasedDDNSService::new(
        CommandLine::new(
            "noip-duc",
            Some(vec![
                "-g".to_string(),
                "all.ddnskey.com".to_string(),
                "--username".to_string(),
                username,
                "--password".to_string(),
                password,
                "--once".to_string(),
            ]),
            None,
            None,
            CmdConfig::Empty
        )
    );

    svc.set_callback(
        Arc::new(|output|
            {
                Box::pin(async move {
                    !output.contains("update failed")
                })
            }
        )
    );

    svc
}

pub fn DuckDNS(domain:String, token:String) -> TokenBasedDDNSService
{
    let mut svc = TokenBasedDDNSService::from_url("https://www.duckdns.org/update".to_string())
    .push_param("domains".to_string(), domain)
    .push_param("token".to_string(), token)
    .push_param("verbose".to_string(), "true".to_string())
    .push_param("ip".to_string(), String::new());

    svc.set_callback(
        Arc::new(|r|{
            Box::pin(async move {
                return if let Some(t) = r.body.as_ref()
                {
                    r.status_code == 200 && t.trim().starts_with("OK")
                } else { false }
            })
        })
    );

    svc
}

pub fn DynuDDNS(username:String, password:String) -> TokenBasedDDNSService
{
    let mut svc = TokenBasedDDNSService::from_url("http://api.dynu.com/nic/update".to_string())
        .push_param("username".to_string(), username)
        .push_param("password".to_string(), password);

    svc.set_callback(
        Arc::new(|r|{
            Box::pin(async move {
                return if let Some(t) = r.body.as_ref()
                {
                    t.trim().starts_with("good")
                } else { false }
            })
        })
    );

    svc
}

pub fn FreeDNS(token:String) -> TokenBasedDDNSService
{
    let mut svc = TokenBasedDDNSService::from_url(format!("https://freedns.afraid.org/dynamic/update.php/{}",token));

    svc.set_callback(
        Arc::new(|r|{
            Box::pin(async move {
                return if let Some(t) = r.body.as_ref()
                {
                    !t.trim().contains("Unable to locate this record")
                } else { true }
            })
        })
    );

    svc
}

pub fn DNSExit(username:String, password:String) -> TokenBasedDDNSService
{
    let mut svc = TokenBasedDDNSService::from_url("https://api.dnsexit.com/dns/ud/".to_string())
        .push_param("host".to_string(), username)
        .push_param("apikey".to_string(), password);

    svc.set_callback(
        Arc::new(|r|{
            Box::pin(async move {
                return if let Some(t) = r.body.as_ref() &&
                    let Ok(j) = serde_json::from_str::<Value>(t.as_str()) &&
                    let Some(o) = j.as_object() &&
                    let Some(c) = o.get("code") &&
                    let Some(code) = c.as_i64()
                {
                    code == 0
                } else { false }
            })
        })
    );

    svc
}

pub fn Dynv6(hostname:String, token:String) -> TokenBasedDDNSService
{
    let mut svc = TokenBasedDDNSService::from_url("https://ipv4.dynv6.com/api/update".to_string())
        .push_param("hostname".to_string(), hostname)
        .push_param("token".to_string(), token)
        .push_param("ipv4".to_string(), "auto".to_string());

    svc.set_callback(
        Arc::new(|r|{
            Box::pin(async move {
                r.status_code == 200
            })
        })
    );

    svc
}


pub fn ClouDNS(token:String) -> TokenBasedDDNSService
{
    let mut svc = TokenBasedDDNSService::from_url("https://ipv4.cloudns.net/api/dynamicURL/".to_string())
        .push_param("q".to_string(), token);

    svc.set_callback(
        Arc::new(|r|{
            Box::pin(async move {
                return if let Some(t) = r.body.as_ref()
                {
                    t.trim().starts_with("OK")
                } else { false }
            })
        })
    );

    svc
}
