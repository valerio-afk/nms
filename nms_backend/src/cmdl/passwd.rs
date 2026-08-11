use super::*;

pub enum UserModAction<S>
{
    ChangeUsername(S,S),
    ChangeUID(S,u32,u32),
    AddGroup(S,S),
    ChangeShell(S,S)
}

pub enum GPasswdAction<S>
{
    RemoveGroup(S,S),
}

pub fn UserAdd<S>(
    username:&str,
    groups:Option<&[&str]>,
    home_dir:Option<S>,
    allow_login: bool,
    config:CmdConfig
) -> CommandLine
where S: AsRef<str> + ToString
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

    args.push(username.to_string());

    CommandLine::new(
        "useradd",
        Some(args),
        Some(Box::new(UserDel(username,false,config.clone()))),
        None,
        config
    )
}

pub fn UserMod<S:AsRef<str>+ToString> (action:UserModAction<S>, revertible:bool,config:CmdConfig) -> CommandLine
{
    let mut args: Vec<String> = Vec::new();
    let mut revert_cmd :Option<Box<CommandLine>> = None;

    match action
    {
        UserModAction::ChangeUsername(old,new) =>
            {
                args.push("-l".to_string());
                args.push(new.to_string());
                args.push(old.to_string());

                if revertible
                {
                    revert_cmd = Some(Box::new(UserMod(UserModAction::ChangeUsername(new,old),false,config.clone())));
                }
            }
        UserModAction::ChangeUID(uname, old, new) =>
            {
                args.push("-u".to_string());
                args.push(format!("{}",new));
                args.push(uname.to_string());

                if revertible
                {
                    revert_cmd = Some(Box::new(UserMod(UserModAction::ChangeUID(uname,new, old),false,config.clone())));
                }
            }
        UserModAction::AddGroup(uname,grpname) =>
            {
                args.push("-aG".to_string());
                args.push(grpname.to_string());
                args.push(uname.to_string());
                
                if revertible
                {
                    revert_cmd = Some(Box::new(GPasswd(GPasswdAction::RemoveGroup(uname, grpname),config.clone())));
                }
            }
        UserModAction::ChangeShell(uname, shell) =>
            {
                args.push("-s".to_string());
                args.push(shell.to_string());
                args.push(uname.to_string());
            }
    }

    CommandLine::new(
        "usermod",
        Some(args),
        revert_cmd,
        None,
        config
    )
}

pub fn UserDel<S:AsRef<str>+ToString> (username:S,keep_home:bool,config:CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();

    if !keep_home
    {
        args.push("-r".to_string());
    }

    args.push(username.to_string());

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

pub fn GPasswd<S:AsRef<str>+ToString>(action:GPasswdAction<S>,config:CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();

    match action
    {
        GPasswdAction::RemoveGroup(uname,grpname) =>
            {
                args.push("-d".to_string());
                args.push(grpname.to_string());
                args.push(uname.to_string());
            }
    }

    CommandLine::new(
        "gpasswd",
        Some(args),
        None,
        None,
        config
    )
}

pub fn ChPasswd<S:AsRef<str>+ToString>(username:S, password:S, config:CmdConfig) -> CommandLine
{
    let data = format!("{}:{}",username.to_string(),password.to_string());

    let cfg = CmdConfig::Provided {
        sudo: config.is_sudo(),
        strict: config.is_strict(),
        stdin: Some(data.as_bytes().to_vec()),
        cwd: None
    };

    CommandLine::new(
        "chpasswd",
        None,
        None,
        None,
        cfg
    )

}