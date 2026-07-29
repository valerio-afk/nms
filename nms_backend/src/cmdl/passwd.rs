use super::*;

pub fn UserAdd(
    username:&String,
    groups:Option<&[&str]>,
    home_dir:Option<&String>,
    allow_login: bool,
    config:CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = vec![
        "-U".to_string(),
        "-s".to_string(),
        if allow_login { "/bin/bash".to_string() } else { "/usr/sbin/nologin".to_string() }
    ];

    if let Some(home) = home_dir
    {
        args.push("-m".to_string());
        args.push("-d".to_string());
        args.push(home.to_string());
    }

    if let Some(g) = groups
    {
        args.push("-G".to_string());
        args.push(g.join(","))
    }

    args.push(username.clone());

    CommandLine::new(
        "useradd",
        Some(args),
        Some(Box::new(UserDel(username,false,config.clone()))),
        None,
        config
    )
}

pub fn UserDel (username:&String,keep_home:bool,config:CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();

    if !keep_home
    {
        args.push("-r".to_string());
    }

    args.push(username.clone());

    CommandLine::new(
        "userdel",
        Some(args),
        None,
        None,
        config
    )
}


pub fn Groups(
    username:&str,
    config:CmdConfig
) -> CommandLine
{
    CommandLine::new(
        "groups",
        Some(vec![username.to_string()]),
        None,
        None,
        config
    )
}

pub fn GetEntPasswd(
    username:Option<&str>,
    config:CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = vec![
        "passwd".to_string()
    ];

    if let Some(uname) = username
    {
        args.push(uname.to_string());
    }

    CommandLine::new(
        "getent",
        Some(args),
        None,
        None,
        config
    )
}