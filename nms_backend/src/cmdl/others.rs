use super::*;

pub fn Mimetype(filename:&String,config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "mimetype",
        Some(vec![filename.clone()]),
        None,
        None, 
        config)
}

pub fn RSync(
    src:&str,
    dst:&str,
    flags:Option<&[&str]>,
    config:CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();

    if let Some(flg) = flags
    {
        for f in flg
        {
            args.push(f.to_string());
        }
    }

    args.extend_from_slice(&[
        src.to_string(),
        dst.to_string()
    ]);

    CommandLine::new(
        "rsync",
        Some(args),
        None,
        None,
        config
    )
}