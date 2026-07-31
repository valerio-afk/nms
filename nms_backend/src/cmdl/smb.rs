use strum::Display;
use crate::cmdl::{CmdConfig, CommandLine};

#[derive(Debug, Display)]
pub enum SMBPasswdAction<S: AsRef<str>+ToString>
{
    #[strum(to_string="a")]
    Add,

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
    S1: AsRef<str>+ToString,
    S2: AsRef<str>+ToString
{
    let mut args:Vec<String> = Vec::new();
    
    if let flag = action.to_string() && (flag.len()>0)
    {
        args.push(format!("-{}", flag));
    }
    
    args.push(username.to_string());
    
    if let SMBPasswdAction::Update(pwd) = action
    {
        config.set_stdin_data(pwd.to_string().as_bytes().to_vec()); 
    }
        
    CommandLine::new(
        "smbpasswd",
        Some(args),
        None,
        None,
        config
    )
}