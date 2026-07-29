use super::*;

pub enum INotifyEvents
{
    Create,
    Modify,
    Delete
}

impl std::fmt::Display for INotifyEvents
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        match self
        {
            INotifyEvents::Create => write!(f,"create"),
            INotifyEvents::Modify => write!(f,"modify"),
            INotifyEvents::Delete => write!(f,"delete"),
        }
    }
}

pub fn INotifyWait(
    path:&str,
    monitor:bool,
    recursive:bool,
    events:Vec<INotifyEvents>,
    format:Option<&str>,
    config:CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();

    if monitor { args.push("-m".to_string()); }
    if recursive { args.push("-r".to_string()); }

    if events.len() > 0
    {
        args.push("-e".to_string());
        args.push(events.iter().map(|x|x.to_string()).collect::<Vec<String>>().join(","));
    }

    if let Some(fmt) = format
    {
        args.push("--format".to_string());
        args.push(fmt.to_string());
    }

    args.push(path.to_string());

    CommandLine::new (
         "inotifywait", 
         Some(args),
         None,
         None,
         config
    )

}