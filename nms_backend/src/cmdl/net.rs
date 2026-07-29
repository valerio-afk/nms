use super::*;

const NMCLI_DEFAULT_PARAMS:&[&str] = &["-c", "no","-t"]; //no colours, terse

pub fn NMCLIDevice(
    subcommand:&str,
    parameters:Option<&[&str]>,
    config:CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = Vec::new(); //vec!["device".to_string(), subcommand];

    for &p in NMCLI_DEFAULT_PARAMS
    {
        args.push(p.to_string());
    }

    args.push("device".to_string());
    args.push(subcommand.to_string());

    if let Some(params) = parameters
    {
        for p in params
        {
            args.push(p.to_string());
        }
    }

    CommandLine::new(
        "nmcli",
        Some(args),
        None,
        None,
        config
    )
}

pub fn NMCLIConnection(
    subcommand:&str,
    parameters:Option<&[&str]>,
    config:CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();

    for &p in NMCLI_DEFAULT_PARAMS
    {
        args.push(p.to_string());
    }

    args.push("connection".to_string());
    args.push(subcommand.to_string());

    if let Some(params) = parameters
    {
        for p in params
        {
            args.push(p.to_string());
        }
    }

    CommandLine::new(
        "nmcli",
        Some(args),
        None,
        None,
        config
    )
}