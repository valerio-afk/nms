use super::*;

pub fn Shutdown(config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "shutdown",
        Some(vec!["-h".to_string(),"now".to_string()]),
        None,
        None,
        config
    )
}

pub fn Reboot(config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "reboot",
        None,
        None,
        None,
        config
    )
}