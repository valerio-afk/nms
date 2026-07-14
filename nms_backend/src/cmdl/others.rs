use super::*;

pub fn Mimetype<'a,'b>(filename:&String,config:Option<&'b CmdConfig<'a>>) -> CommandLine<'a,'b>
{
    CommandLine::new(
        "mimetype",
        Some(vec![filename.clone()]),
        None,
        None, 
        config)
}

