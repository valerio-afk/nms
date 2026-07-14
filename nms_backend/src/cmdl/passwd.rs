use super::*;

pub fn UserAdd<'a,'b>(
    username:&String,
    groups:Option<&[&str]>,
    home_dir:Option<&String>,
    allow_login: bool,
    config:Option<&'b CmdConfig<'a>>
) -> CommandLine<'a,'b>
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
        Some(Box::new(UserDel(username,false,config))),
        None,
        config
    )
}

pub fn UserDel<'a,'b> (username:&String,keep_home:bool,config:Option<&'b CmdConfig<'a>>) -> CommandLine<'a,'b>
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


pub fn Groups<'a,'b>(
    username:&str,
    config:Option<&'b CmdConfig<'a>>
) -> CommandLine<'a,'b>
{
    CommandLine::new(
        "groups",
        Some(vec![username.to_string()]),
        None,
        None,
        config
    )
}