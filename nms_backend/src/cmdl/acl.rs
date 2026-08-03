use std::fmt::{Display, Formatter};
use crate::cmdl::{CmdConfig, CommandLine};
use crate::cmdl::coreutils::{OSGroup, OSUser, POSIXPermissions};

pub enum AclIdentity
{
    User(OSUser),
    Group(OSGroup),
}

impl Display for AclIdentity
{
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result
    {
        match self
        {
            AclIdentity::User(u) => match u
            {
                OSUser::ID(id) => write!(f, "u:{}", id),
                OSUser::Name(name) => write!(f, "u:{}", name),
                OSUser::Empty => write!(f, ""),
            },
            AclIdentity::Group(u) => match u
            {
                OSUser::ID(id) => write!(f, "g:{}", id),
                OSUser::Name(name) => write!(f, "g:{}", name),
                OSUser::Empty => write!(f, ""),
            },
        }
    }
}

pub fn SetfAcl<S: AsRef<str>+ToString>(
    identify: AclIdentity,
    permission:POSIXPermissions,
    path: S,
    recursive: bool,
    default: bool,
    config: CmdConfig
) -> CommandLine
{
    let mut acl_perm: String = String::new();
    
    if default
    {
        acl_perm.push_str("d:");
    }
    
    acl_perm.push_str(identify.to_string().as_str());
    acl_perm.push(':');
    
    acl_perm.push_str(permission.to_string().as_str());
    
    let mut args:Vec<String> = Vec::new();
    if recursive
    {
        args.push("-R".to_string());
    }

    args.push("-m".to_string());
    args.push(acl_perm);
    args.push(path.to_string());
    
    CommandLine::new(
        "setfacl",
        Some(args),
        None,
        None,
        config
    )
}