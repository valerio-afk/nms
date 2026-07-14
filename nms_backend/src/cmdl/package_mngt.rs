use std::fmt::write;

use super::*;

pub struct PackageMngtUpgradeParameters
{
    dry_run:bool,
    yes: bool
}

pub enum PackageManagerActions
{
    Update,
    Upgrade(PackageMngtUpgradeParameters)
}

struct AptActions;
struct DnfActions;


impl CmdFlag<PackageManagerActions> for AptActions 
{
    fn flag(action:&PackageManagerActions) ->  &'static str
    {
        match action 
        {
            PackageManagerActions::Update => "update",
            PackageManagerActions::Upgrade(_)=> "upgrade"
        }
    }
}

impl CmdFlag<PackageManagerActions> for  DnfActions 
{
    fn flag(action:&PackageManagerActions) ->  &'static str
    {
        match action 
        {
            PackageManagerActions::Update => "check-update",
            PackageManagerActions::Upgrade(_) => "upgrade"
        }
    }
}

pub fn PipInstall<'a,'b>
(
    packages:Option<&[&String]>,
    requirements:Option<&String>,
    local_env:bool,
    config:Option<&'b CmdConfig<'a>>
) -> CommandLine<'a,'b>
{
    let mut args:Vec<String> = vec!["install".to_string()];
    let mut pip= "";

    if let Some(r) = requirements
    {
        args.push("-r".to_string());
        args.push(r.to_string());
    }

    if let Some(pkg) = packages
    {
        for &p in pkg
        {
            args.push(p.clone());
        }
    }

    if local_env
    {
        let mut panic = false;
        if let Some(cfg) = config
        {
            if let Some(_) = &cfg.cwd
            {
                pip = "./pip";
            }
            else {panic=true;}
        }
        else {panic=true;}

        if panic 
        { 
            panic!("You must specify `cwd` in the configuration to run a local environment"); 
        }
    }
    else
    {
        pip = "pip";
    }

    CommandLine::new(
        pip,
        Some(args),
        None,
        None,
        config
    )
}



pub fn AptGet<'a,'b>(action:PackageManagerActions,config:Option<&'b CmdConfig<'a>>) -> CommandLine<'a,'b>
{
    let mut args:Vec<String> = vec![AptActions::flag(&action).to_string()];

    if let PackageManagerActions::Upgrade(params) = action
    {
        if params.dry_run { args.push("--just-print".to_string()); }
        if params.yes { args.push("-y".to_string()); }
    }

    CommandLine::new(
        "apt-get",
        Some(args),
        None,
        None,
        config
    )
}

pub fn DNF<'a,'b>(action:PackageManagerActions,config:Option<&'b CmdConfig<'a>>) -> CommandLine<'a,'b>
{
    let mut args:Vec<String> = vec![DnfActions::flag(&action).to_string()];

    if let PackageManagerActions::Upgrade(params) = action
    {
        args.push("--refresh".to_string());
        if params.yes { args.push("-y".to_string()); }
    }

    CommandLine::new(
        "dnf",
        Some(args),
        None,
        None,
        config
    )
}