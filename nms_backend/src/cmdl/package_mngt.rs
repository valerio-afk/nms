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

pub fn PipInstall
(
    packages:Option<&[&String]>,
    requirements:Option<&String>,
    local_env:bool,
    config:CmdConfig
) -> CommandLine
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
        if config.is_provided()
        {
            if let Some(_) = &config.cwd()
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



pub fn AptGet(action:PackageManagerActions,config:CmdConfig) -> CommandLine
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

pub fn DNF(action:PackageManagerActions,config:CmdConfig) -> CommandLine
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