use super::*;


pub enum SystemctlAction
{
    Enable,
    Disable,
    Start,
    Stop,
    Restart,
    Mask,
    Unmask,
    IsActive
}

impl std::fmt::Display for SystemctlAction 
{
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result 
    {
        match self 
        {
            SystemctlAction::Enable => write!(f,"enable"),
            SystemctlAction::Disable => write!(f,"disable"),
            SystemctlAction::Start => write!(f,"start"),
            SystemctlAction::Stop => write!(f,"stop"),
            SystemctlAction::Restart => write!(f,"restart"),
            SystemctlAction::Mask => write!(f,"mask"),
            SystemctlAction::Unmask => write!(f,"unmask"),
            SystemctlAction::IsActive => write!(f,"is-active"),
        }
    }
}


pub fn Journalctl
(
    service:&String,
    grep:Option<&String>,
    since:Option<&String>,
    until:Option<&String>,
    config:CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = vec![
        "-u".to_string(),
        service.clone(),
        "-o".to_string(),
        "cat".to_string()
    ];

    if let Some(pattern) = grep
    {
        args.push("--grep".to_string());
        args.push(pattern.clone());
    }

    if let Some(time) = since
    {
        args.push("--since".to_string());
        args.push(time.clone());
    }

    if let Some(time) = until
    {
        args.push("--until".to_string());
        args.push(time.clone());
    }

    CommandLine::new(
        "journalctl",
        Some(args),
        None,
        None,
        config
    )
}

pub fn Systemctl<S: AsRef<str> + ToString>
(
    service:S,
    action:&SystemctlAction,
    revertible:bool,
    config:CmdConfig
) -> CommandLine
{
    let mut revert_cmd:Option<CommandLine> = None;

    let service_name = service.to_string();

    if revertible
    {
        revert_cmd = match action
            {
                SystemctlAction::Enable => Some(Systemctl(service,&SystemctlAction::Disable,false,config.clone())),
                SystemctlAction::Disable => Some(Systemctl(service,&SystemctlAction::Enable,false,config.clone())),
                SystemctlAction::Start => Some(Systemctl(service,&SystemctlAction::Stop,false,config.clone())),
                SystemctlAction::Stop => Some(Systemctl(service,&SystemctlAction::Start,false,config.clone())),
                SystemctlAction::Restart => None,
                SystemctlAction::Mask => Some(Systemctl(service,&SystemctlAction::Unmask,false,config.clone())),
                SystemctlAction::Unmask => Some(Systemctl(service,&SystemctlAction::Mask,false,config.clone())),
                SystemctlAction::IsActive => None
            }
    }

    CommandLine::new(
        "journalctl",
        Some(
            vec![
                action.to_string(),
                service_name,
            ]
        ),
        if let Some(cmd) = revert_cmd { Some(Box::new(cmd)) } else {None}
        ,
        None,
        config
    )
}