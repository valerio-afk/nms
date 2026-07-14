use super::*;

pub fn Shutdown<'a,'b>(config:Option<&'b CmdConfig<'a>>) -> CommandLine<'a,'b>
{
    CommandLine::new(
        "shutdown",
        Some(vec!["-h".to_string(),"now".to_string()]),
        None,
        None,
        config
    )
}

pub fn Reboot<'a,'b>(config:Option<&'b CmdConfig<'a>>) -> CommandLine<'a,'b>
{
    CommandLine::new(
        "reboot",
        None,
        None,
        None,
        config
    )
}