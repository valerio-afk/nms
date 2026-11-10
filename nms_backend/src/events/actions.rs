use super::{Events, ContextVariables, EventParameterTypes, EventParameterValues};
use serde::{Serialize,Deserialize};
use strum::VariantArray;
use crate::backend::EventActionSpec;

#[derive(Debug, Deserialize, Serialize)]
pub enum ActionCategories
{
    Notification,
    Execution,
    File,
}

impl std::fmt::Display for ActionCategories
{
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result
    {
        match self
        {
            ActionCategories::Notification => f.write_str("notification"),
            ActionCategories::Execution => f.write_str("execution"),
            ActionCategories::File => f.write_str("file"),
        }
    }
}

#[derive(Debug, Serialize, Deserialize, VariantArray)]
pub enum EventActions
{
    SendTo,
    SendToAll,
    SendToAdmin,
    RunScript,
    ChangeOwner,
    ChangePermissions
}

impl std::fmt::Display for EventActions
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        match self
        {
            EventActions::SendTo => write!(f, "send_to"),
            EventActions::SendToAll => write!(f, "send_to_all"),
            EventActions::SendToAdmin => write!(f, "send_to_admins"),
            EventActions::RunScript => write!(f, "run_script"),
            EventActions::ChangeOwner => write!(f, "change_owner"),
            EventActions::ChangePermissions => write!(f, "change_permissions"),
        }
    }
}

impl std::str::FromStr for EventActions
{
    type Err = ();

    fn from_str(s: &str) -> Result<Self, Self::Err> 
    {
        match s
        {
            "send_to" => Ok(EventActions::SendTo),
            "send_to_all" => Ok(EventActions::SendToAll),
            "send_to_admins" => Ok(EventActions::SendToAdmin),
            "run_script" => Ok(EventActions::RunScript),
            "change_owner" => Ok(EventActions::ChangeOwner),
            "change_permissions" => Ok(EventActions::ChangePermissions),
            _ => Err(())
        }    
    }
}

impl EventActions
{
    pub fn get_events(&self) -> Vec<Events>
    {
        match self
        {
            EventActions::SendTo => vec![
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
            EventActions::SendToAll => vec![
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
            EventActions::SendToAdmin => vec![
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

            EventActions::RunScript => vec![
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
            EventActions::ChangeOwner => vec![
                Events::FileCreated,
                Events::FileDeleted,
                Events::FileModified
                
            ],
            EventActions::ChangePermissions => vec![
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
            EventActions::SendToAll => vec![ContextVariables::User],
            EventActions::SendToAdmin => vec![ContextVariables::User],
            EventActions::ChangeOwner => vec![
                ContextVariables::User,
                ContextVariables::Group,
                ContextVariables::Permissions,
            ],
            EventActions::ChangePermissions => vec![
                ContextVariables::User,
                ContextVariables::Group,
                ContextVariables::Permissions,
            ],
            _ => vec![],
        }
    }

    pub fn get_action_parameters(&self) -> Vec<EventParameterTypes>
    {
        match self
        {
            EventActions::SendTo => vec![EventParameterTypes::User, EventParameterTypes::Notification],
            EventActions::SendToAdmin | EventActions::SendToAll => vec![EventParameterTypes::Notification],
            EventActions::RunScript => vec![EventParameterTypes::RunScript],
            EventActions::ChangeOwner => vec![EventParameterTypes::FileOwnership],
            EventActions::ChangePermissions => vec![EventParameterTypes::FilePermission],
            _ => vec![]
        }
    }

    pub fn get_context_variables_from_event(&self, event:&Events) -> Vec<ContextVariables>
    {
        let mut ctx =  event.get_context_variables();
        ctx.extend(self.get_context_variables());

        ctx
    }

    pub fn get_category(&self) -> ActionCategories
    {
        match self
        {
            EventActions::SendTo | EventActions::SendToAdmin | EventActions::SendToAll => ActionCategories::Notification,
            EventActions::RunScript => ActionCategories::Execution,
            EventActions::ChangeOwner | EventActions::ChangePermissions => ActionCategories::File
        }
    }
}