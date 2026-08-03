use super::{Events,ContextVariables};
use serde::{Serialize,Deserialize};


#[derive(Debug, Serialize, Deserialize)]

pub enum UserDefinedActions
{
    SendTo,
    SendToAll,
    SendToAdmin,
    RunScript,
    ChangeOwner,
    ChangePermissions
}

impl std::fmt::Display for UserDefinedActions
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        match self
        {
            UserDefinedActions::SendTo => write!(f,"send_to"),
            UserDefinedActions::SendToAll => write!(f,"send_to_all"),
            UserDefinedActions::SendToAdmin => write!(f,"send_to_admins"),
            UserDefinedActions::RunScript => write!(f,"run_script"),
            UserDefinedActions::ChangeOwner => write!(f,"change_owner"),
            UserDefinedActions::ChangePermissions => write!(f,"change_permissions"),
        }
    }
}

impl std::str::FromStr for UserDefinedActions
{
    type Err = ();

    fn from_str(s: &str) -> Result<Self, Self::Err> 
    {
        match s
        {
            "send_to" => Ok(UserDefinedActions::SendTo),
            "send_to_all" => Ok(UserDefinedActions::SendToAll),
            "send_to_admins" => Ok(UserDefinedActions::SendToAdmin),
            "run_script" => Ok(UserDefinedActions::RunScript),
            "change_owner" => Ok(UserDefinedActions::ChangeOwner),
            "change_permissions" => Ok(UserDefinedActions::ChangePermissions),
            _ => Err(())
        }    
    }
}

impl UserDefinedActions
{
    pub fn get_events(&self) -> Vec<Events>
    {
        match self
        {
            UserDefinedActions::SendTo => vec![
                Events::SystemStartup,
                Events::SystemReboot,
                Events::SystemPoweroff,
                Events::SystemShutdown,
                Events::SystemUpdates,
                Events::SystemUpgrade,
                Events::PoolMount,
                Events::PoolUnmount,
                Events::UserLoggedIn,
                Events::UserCreated,
                Events::UserDeleted,
                Events::AccessEnabled,
                Events::AccessDisabled,
                Events::VPNEnabled,
                Events::VPNDisabled,
                Events::FileShared

            ],
            UserDefinedActions::SendToAll => vec![
                Events::SystemStartup,
                Events::SystemReboot,
                Events::SystemPoweroff,
                Events::SystemShutdown,
                Events::SystemUpdates,
                Events::SystemUpgrade,
                Events::PoolMount,
                Events::PoolUnmount,
                Events::UserLoggedIn,
                Events::UserCreated,
                Events::UserDeleted,
                Events::AccessEnabled,
                Events::AccessDisabled,
                Events::VPNEnabled,
                Events::VPNDisabled,


            ],
            UserDefinedActions::SendToAdmin => vec![
                Events::SystemStartup,
                Events::SystemReboot,
                Events::SystemPoweroff,
                Events::SystemShutdown,
                Events::SystemUpdates,
                Events::SystemUpgrade,
                Events::PoolMount,
                Events::PoolUnmount,
                Events::UserLoggedIn,
                Events::UserCreated,
                Events::UserDeleted,
                Events::AccessEnabled,
                Events::AccessDisabled,
                Events::VPNEnabled,
                Events::VPNDisabled,


            ],
            UserDefinedActions::RunScript => vec![
                Events::SystemStartup,
                Events::SystemReboot,
                Events::SystemPoweroff,
                Events::SystemShutdown,
                Events::SystemUpdates,
                Events::SystemUpgrade,
                Events::Timer,
                Events::PoolMount,
                Events::PoolUnmount,
                Events::UserLoggedIn,
                Events::UserCreated,
                Events::UserDeleted,
                Events::AccessEnabled,
                Events::AccessDisabled,
                Events::VPNEnabled,
                Events::VPNDisabled,
                Events::FileShared

            ],
            UserDefinedActions::ChangeOwner => vec![
                Events::FileCreated,
                Events::FileDeleted,
                Events::FileModified
                
            ],
            UserDefinedActions::ChangePermissions => vec![
                Events::FileCreated,
                Events::FileDeleted,
                Events::FileModified
                
            ],
        }
    }

    pub fn get_context_variables(&self) -> Vec<ContextVariables>
    {
        match self
        {
            UserDefinedActions::SendToAll => vec![ContextVariables::User],
            UserDefinedActions::SendToAdmin => vec![ContextVariables::User],
            UserDefinedActions::ChangeOwner => vec![
                ContextVariables::User,
                ContextVariables::Group,
                ContextVariables::Permissions,
            ],
            UserDefinedActions::ChangePermissions => vec![
                ContextVariables::User,
                ContextVariables::Group,
                ContextVariables::Permissions,
            ],
            _ => vec![],
        }
    }

    pub fn get_context_variables_from_event(&self, event:&Events) -> Vec<ContextVariables>
    {
        let mut ctx =  event.get_context_variables();
        ctx.extend(self.get_context_variables());

        return ctx;
    }
}