use std::fmt::Display;
use strum::Display;
use crate::cmdl::{CmdConfig, CommandLine};

#[derive(Debug, Display)]
pub enum SMBPasswdAction<S: AsRef<str>+ToString>
{
    #[strum(to_string="a")]
    Add(S),

    #[strum(to_string="x")]
    Delete,

    #[strum(to_string="")]
    Update(S),

    #[strum(to_string="d")]
    Disable,

    #[strum(to_string="e")]
    Enable,
}

pub fn SMBPasswd<S1,S2>(action:SMBPasswdAction<S1>, username:S2, mut config:CmdConfig) -> CommandLine
where
    S1: AsRef<str>+ToString+Display,
    S2: AsRef<str>+ToString+Display
{
    let mut args:Vec<String> = Vec::new();
    
    if let flag = action.to_string() && (flag.len()>0)
    {
        args.push(format!("-{}", flag));
    }
    
    args.push(username.to_string());

    
    match action
    {
        SMBPasswdAction::Update(pwd) | SMBPasswdAction::Add(pwd) =>
            {
                let pwd_data = format!("{}\n{}\n",pwd,pwd);
                config.set_stdin_data(pwd_data.as_bytes().to_vec());
            }
        _ => (),
    }
        
    CommandLine::new(
        "smbpasswd",
        Some(args),
        None,
        None,
        config
    )
}