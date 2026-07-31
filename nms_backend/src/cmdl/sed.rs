use strum::{Display};
use crate::cmdl::{CmdConfig, CommandLine};

#[derive(Debug, PartialEq, Display)]
pub enum SedFlags
{
    #[strum(to_string="i")]
    InPlace,
}

pub fn Sed<S1,S2>(flags:Option<Vec<SedFlags>>,pattern:S1,filename:Option<S2>,config:CmdConfig) -> CommandLine
where
    S1:AsRef<str>+ToString,
    S2:AsRef<str>+ToString,
{
    let mut args = Vec::new();

    if let Some(f) = flags
    {
        for flag in f
        {
            args.push(format!("-{}", flag.to_string()));
        }
    }

    args.push(pattern.to_string());
    if let Some(fname) = filename
    {
        args.push(fname.to_string());
    }
    else
    {
        if config.stdin_data().is_none()
        {
            panic!("No input filename or piped data provided for grep");
        }
    }

    CommandLine::new(
        "sed",
        Some(args),
        None,
        None,
        config
    )


}