use strum::Display;
use crate::cmdl::{CmdConfig, CommandLine};

#[derive(Display)]
#[strum(serialize_all = "lowercase")]
pub enum DKMSActions
{
    Autoinstall,
}

#[derive(Display)]
pub enum DepModActions
{
    #[strum(to_string="a")]
    All,
}

#[derive(Display)]
pub enum ModInfoActions
{
    #[strum(to_string="n")]
    Filename(String),
}

pub fn DKMS(action:DKMSActions,config:CmdConfig) -> CommandLine
{
    let args = vec![action.to_string()];

    CommandLine::new(
        "dkms",
        Some(args),
        None,
        None,
        config
    )
}

pub fn DepMod(actions:Vec<DepModActions>,config:CmdConfig) -> CommandLine
{
    let args = actions.iter().map(|x|format!("-{}",x.to_string())).collect::<Vec<String>>();

    CommandLine::new(
        "depmod",
        Some(args),
        None,
        None,
        config
    )
}

pub fn ModProbe (module:String,config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "modprobe",
        Some(vec![module]),
        None,
        None,
        config
    )
}

pub fn ModInfo(action:Vec<ModInfoActions>,config:CmdConfig) -> CommandLine
{
    let mut args = Vec::new();

    for a in action.iter()
    {
        args.push(format!("-{}", a.to_string()));

        match a
        {
            ModInfoActions::Filename(fname) => args.push(format!("{}", fname)),
        }
    }


    CommandLine::new(
        "modinfo",
        Some(args),
        None,
        None,
        config
    )
}
