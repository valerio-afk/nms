use strum::{Display};
use crate::cmdl::{CmdConfig, CommandLine};

#[derive(Debug, PartialEq, Display)]
pub enum GrepFlags
{
    #[strum(to_string="F")]
    FixedString,
    #[strum(to_string="x")]
    WholeLine,
    #[strum(to_string="q")]
    Quiet
}

pub fn Grep<S1,S2>(flags:Option<Vec<GrepFlags>>,pattern:S1,filename:Option<S2>,config:CmdConfig) -> CommandLine
where
    S1:AsRef<str>+ToString,
    S2:AsRef<str>+ToString,
{
    let mut args = Vec::new();

    if let Some(f) = flags
    {
        args.push(format!("-{}", f.iter().map(|x|x.to_string()).collect::<Vec<String>>().join("")));
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
        "grep",
        Some(args),
        None,
        None,
        config
    )


}