use std::collections::HashMap;

use super::*;
use super::coreutils::{OSUser,OSGroup};

pub enum DockerRestart
{
    No,
    Always,
    UnlessStopped,
    OnFailuereWithRetries(Option<u32>)
}

impl std::fmt::Display for DockerRestart
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        match self
        {
            DockerRestart::No => write!(f,"no"),
            DockerRestart::Always => write!(f,"always"),
            DockerRestart::UnlessStopped => write!(f,"unless-stopped"),
            DockerRestart::OnFailuereWithRetries(retries) => 
                {
                    if let Some(r) = retries { write!(f,"on-failure:{r}") }
                    else { write!(f,"on-failure") }
                }
        }    
    }
}



pub fn DockerRun(
    image_name:&str,
    container_name: &str,
    mount:Option<HashMap<&str,&str>>,
    env:Option<HashMap<&str,&str>>,
    port_forwarding:Option<&[(u32,u32,Option<&str>)]>,
    user:Option<(OSUser,OSGroup)>,
    detach:bool,
    remove:bool,
    restart:Option<DockerRestart>,
    config: CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = vec!["run".to_string()];

    if let Some(mp) = mount
    {
        for (vol,host) in &mp
        {
            args.push("-v".to_string());
            args.push(format!("{vol}:{host}"));
        }
    }

    if let Some(e) = env
    {
        for (k,v) in &e
        {
            args.push("--env".to_string());
            args.push(format!("{k}={v}"));
        }
    }

    if let Some(ports) = port_forwarding
    {
        for (from,to,prot) in ports
        {
            let mut p = format!("{from}:{to}");

            if let Some(x) = prot
            {
                p.push_str(x);
            }

            args.push("-p".to_string());
            args.push(p);
        }
    }

   
    args.push("--name".to_string());
    args.push(container_name.to_string());

    if detach {args.push("--detach".to_string());}
    if remove {args.push("--rm".to_string());}

    if let Some(r) = restart
    {
        args.push("--restart".to_string());
        args.push(r.to_string());
    }

    if let Some((u,g)) = user
    {
        let mut user_spec = String::new();
                
        match u
        {
            OSUser::ID(uid) => user_spec.push_str(&format!("{uid}")),
            OSUser::Name(uname) => user_spec.push_str(&format!("{uname}")),
            OSUser::Empty => ()
        }

        if user_spec.len()>0
        {
            match g
            {
                OSUser::ID(gid) => user_spec.push_str(&format!(":{gid}")),
                OSUser::Name(gname) => user_spec.push_str(&format!(":{gname}")),
                OSUser::Empty => ()
            }

            args.push(format!("--user={user_spec}"));
        }
        
    }

    args.push(image_name.to_string());

    CommandLine::new
    (
        "docker",
        Some(args),
        Some(Box::new(
            DockerStop(container_name,config.clone())
        )),
        None,
        config
    )
}

pub fn DockerStop(identifier:&str,config: CmdConfig) -> CommandLine
{
    CommandLine::new(
        "docker",
        Some(vec!["stop".to_string(),identifier.to_string()]),
        None,
        None,
        config
    )
}

pub fn DockerRemove(identifier:&str,config: CmdConfig) -> CommandLine
{
    CommandLine::new(
        "docker",
        Some(vec!["rm".to_string(),identifier.to_string()]),
        None,
        None,
        config
    )
}

pub fn DockerInspect
(
    identifier:&str,
    parameters:&[&str],
    config: CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = vec!["inspect".to_string()];

    for p in parameters
    {
        args.push(p.to_string())
    }

    args.push(identifier.to_string());

    CommandLine::new(
        "docker",
        Some(args),
        None,
        None,
        config
    )
}