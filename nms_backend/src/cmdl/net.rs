use super::*;

const NMCLI_DEFAULT_PARAMS:&[&str] = &["-c", "no","-t"]; //no colours, terse

pub fn NMCLIDevice<'a,'b>(
    subcommand:&String,
    parameters:Option<&[&String]>,
    config:Option<&'b CmdConfig<'a>>
) -> CommandLine<'a,'b>
{
    let mut args:Vec<String> = vec!["device".to_string(), subcommand.clone()];

    for &p in NMCLI_DEFAULT_PARAMS
    {
        args.push(p.to_string());
    }

    if let Some(params) = parameters
    {
        for &p in params
        {
            args.push(p.clone());
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

pub fn NMCLIConnection<'a,'b>(
    subcommand:&String,
    parameters:Option<&[&String]>,
    config:Option<&'b CmdConfig<'a>>
) -> CommandLine<'a,'b>
{
    let mut args:Vec<String> = vec!["connection".to_string(), subcommand.clone()];

    for &p in NMCLI_DEFAULT_PARAMS
    {
        args.push(p.to_string());
    }

    if let Some(params) = parameters
    {
        for &p in params
        {
            args.push(p.clone());
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