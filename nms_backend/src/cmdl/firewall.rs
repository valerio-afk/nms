use std::fmt::Display;
use strum::Display;
use crate::cmdl::{CmdConfig, CommandLine};
use crate::cmdl::selinux::Protocol;

#[derive(Debug)]
pub enum PortParseError
{
    Parse(String),
    PortMinParse(String),
    PortMaxParse(String),
}

impl Display for PortParseError
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result
    {
        match &self
        {
            PortParseError::Parse(s) => write!(f, "Failed to parse port: {}", s),
            PortParseError::PortMinParse(s) => write!(f, "Failed to parse port min: {}", s),
            PortParseError::PortMaxParse(s) => write!(f, "Failed to parse port max: {}", s),
        }
    }
}

impl std::error::Error for PortParseError {}

#[derive(Debug,PartialEq,Eq, Clone)]
pub enum FirewallPort
{
    Port(u32),
    PortRange(u32,u32)
}

impl std::fmt::Display for FirewallPort
{
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result
    {
        match &self
        {
            FirewallPort::Port(p) => write!(f, "{}", p),
            FirewallPort::PortRange(p_min, p_max) => write!(f, "{}-{}", p_min, p_max)
        }
    }
}

impl std::str::FromStr for FirewallPort
{
    type Err = PortParseError;
    fn from_str(s: &str) -> Result<Self, Self::Err>
    {
        let try_single_port = s.parse::<u32>();
        if let Ok(single) = try_single_port { return Ok(FirewallPort::Port(single)); }

        let tokens = s.split("-").collect::<Vec<&str>>();

        if tokens.len()==2
        {
            let p_min = tokens[0].parse::<u32>();
            let p_max = tokens[1].parse::<u32>();

            if let Ok(p1) = p_min && let Ok(p2) = p_max
            {
                return Ok(FirewallPort::PortRange(p1, p2));
            }

            if p_min.is_err()
            {
                return Err(PortParseError::PortMinParse(tokens[0].to_string()));
            }
            if p_max.is_err()
            {
                return Err(PortParseError::PortMaxParse(tokens[1].to_string()));
            }
        }

        Err(PortParseError::Parse(s.to_string()))
    }
}

#[derive(Debug, Display, PartialEq, Clone)]
pub enum FirewallAction
{
    #[strum(to_string="add-port")]
    AddPort(FirewallPort,Protocol),
    #[strum(to_string="remove-port")]
    RemovePort(FirewallPort,Protocol),
    #[strum(to_string="add-service")]
    AddService(String),
    #[strum(to_string="remove-service")]
    RemoveService(String),
    #[strum(to_string="reload")]
    Reload,
    #[strum(to_string="state")]
    State
}

pub fn Firewall(
    action: FirewallAction,
    permanent: bool,
    revertible: bool,
    config: CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();
    let mut revert_cmd:Option<Box<CommandLine>> = None;

    let mut add_permanent = permanent;

    match &action
    {
        FirewallAction::Reload|FirewallAction::State =>
        {
            add_permanent = false;
            args.push(action.to_string());
        }
        FirewallAction::AddPort(port,proto)|FirewallAction::RemovePort(port,proto) =>
        {
            args.push(format!("--{}={}/{}",action.to_string(), port.to_string(),proto.to_string()));

            if revertible
            {
                match action
                {
                    FirewallAction::AddPort(_,_) => { revert_cmd = Some(Box::new(Firewall(FirewallAction::RemovePort(port.clone(),proto.clone()), permanent, false, config.clone()))); }
                    FirewallAction::RemovePort(_,_) => { revert_cmd = Some(Box::new(Firewall(FirewallAction::AddPort(port.clone(),proto.clone()), permanent, false, config.clone()))); }
                    _ => ()
                }
            }
        }
        FirewallAction::AddService(service)|FirewallAction::RemoveService(service) =>
        {
            args.push(format!("--{}={}",action.to_string(), service));

            if revertible
            {
                match action
                {
                    FirewallAction::AddService(_) => { revert_cmd = Some(Box::new(Firewall(FirewallAction::RemoveService(service.clone()), permanent, false, config.clone()))); }
                    FirewallAction::RemoveService(_) => { revert_cmd = Some(Box::new(Firewall(FirewallAction::AddService(service.clone()), permanent, false, config.clone()))); }
                    _ => ()
                }
            }
        }
    }

    if add_permanent
    {
        args.push("--permanent".to_string());
    }

    CommandLine::new(
        "firewall-cmd",
        Some(args),
        revert_cmd,
        None,
        config
    )
}