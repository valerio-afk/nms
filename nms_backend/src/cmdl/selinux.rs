use strum::{Display, EnumString};
use crate::cmdl::{CmdConfig, CommandLine};

#[derive(Debug, PartialEq, Display, Clone, EnumString)]
#[strum(serialize_all="lowercase")]
pub enum Protocol
{
    TCP,
    UDP
}
#[derive(Debug, PartialEq, Display)]
pub enum SelinuxManagePortAction
{
    #[strum(to_string="a")]
    Add,
    #[strum(to_string="d")]
    Remove,
    #[strum(to_string="m")]
    Edit,
    #[strum(to_string="l")]
    List
}

#[derive(Debug, PartialEq, Display)]
pub enum SelinuxManageContextAction
{
    #[strum(to_string="a")]
    Add,
    #[strum(to_string="d")]
    Remove,
    #[strum(to_string="l")]
    List
}

pub fn SelinuxManagePort<S:AsRef<str>+ToString>(
    action: SelinuxManagePortAction,
    port_type: Option<S>,
    port: Option<u32>,
    old_port: Option<u32>,
    protocol: Option<Protocol>,
    reversible: bool,
    config: CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = vec!["semanage".to_string(),"port".to_string(),action.to_string()];
    let mut revert_cmd:Option<Box<CommandLine>> = None;


    if action == SelinuxManagePortAction::List
    {
        args.push("--noheading".to_string());
    }
    else
    {
        if let Some(t) = &port_type
        {
            args.push("-t".to_string());
            args.push(t.to_string());
        }

        if let Some(proto) = &protocol
        {
            args.push("-p".to_string());
            args.push(proto.to_string());
        }



        if let Some(p) = port
        {
            args.push(format!("{}",p));
        }

        if reversible
        {
            match action
            {
                SelinuxManagePortAction::Add =>{
                    revert_cmd = Some(
                        Box::new(
                            SelinuxManagePort(
                                SelinuxManagePortAction::Remove,
                                port_type,
                                port,
                                None,
                                protocol,
                                false,
                                config.clone()
                            )
                        )
                    );
                }
                SelinuxManagePortAction::Remove =>{
                    revert_cmd = Some(
                        Box::new(
                            SelinuxManagePort(
                                SelinuxManagePortAction::Add,
                                port_type,
                                port,
                                None,
                                protocol,
                                false,
                                config.clone()
                            )
                        )
                    );
                }
                SelinuxManagePortAction::Edit =>{
                    if old_port.is_some()
                    {
                        revert_cmd = Some(
                            Box::new(
                                SelinuxManagePort(
                                    SelinuxManagePortAction::Edit,
                                    port_type,
                                    old_port,
                                    None,
                                    protocol,
                                    false,
                                    config.clone()
                                )
                            )
                        );
                    }
                }
                _ => ()
            }
        }
    }

    CommandLine::new(
        "semanage",
        Some(args),
        revert_cmd,
        None,
        config
    )
}

pub fn SelinuxManageContext<S1,S2>
(
    action: SelinuxManageContextAction,
    context: Option<S1>,
    file_spec: Option<S2>,
    reversible: bool,
    config: CmdConfig
) -> CommandLine
where
    S1: AsRef<str>+ToString,
    S2: AsRef<str>+ToString,
{
    let mut args:Vec<String> = vec!["semanage".to_string(),"fcontext".to_string(),action.to_string()];
    let mut revert_cmd:Option<Box<CommandLine>> = None;


    if action == SelinuxManageContextAction::List
    {
        args.push("--noheading".to_string());
    }
    else
    {
        if let Some(t) = &context
        {
            args.push("-t".to_string());
            args.push(t.to_string());
        }


        if let Some(f) = &file_spec
        {
            args.push(format!("{}",f.to_string()));
        }

        if reversible
        {
            match action
            {
                SelinuxManageContextAction::Add =>{
                    revert_cmd = Some(
                        Box::new(
                            SelinuxManageContext(
                                SelinuxManageContextAction::Remove,
                                context,
                                file_spec,
                                false,
                                config.clone()
                            )
                        )
                    );
                }
                SelinuxManageContextAction::Remove =>{
                    revert_cmd = Some(
                        Box::new(
                            SelinuxManageContext(
                                SelinuxManageContextAction::Add,
                                context,
                                file_spec,
                                false,
                                config.clone()
                            )
                        )
                    );
                }
                _ => ()
            }
        }
    }

    CommandLine::new(
        "semanage",
        Some(args),
        revert_cmd,
        None,
        config
    )
}


pub fn SeLinuxSetBool<S:AsRef<str>+ToString>(property: S, value: bool,permanent:bool,revertible:bool,config: CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();
    let mut revert_cmd:Option<Box<CommandLine>> = None;

    if permanent
    {
        args.push("-P".to_string());
    }

    args.push(property.to_string());
    args.push((if value {"1"} else {"0"}).to_string());

    if revertible
    {
        revert_cmd = Some(Box::new(
            SeLinuxSetBool(property,!value,permanent,revertible, config.clone())
        ));
    }

    CommandLine::new(
        "setsebool",
        Some(args),
        revert_cmd,
        None,
        config
    )
}

pub fn RestoreContext<S:AsRef<str>+ToString>(path:S, recursive:bool, config: CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();
    
    if recursive
    {
        args.push("-R".to_string());
    }
    
    args.push(path.to_string());
    
    CommandLine::new(
        "restorecon",
        Some(args),
        None,
        None,
        config
    )
    
    
}