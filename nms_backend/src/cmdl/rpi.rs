use super::*;

pub enum VideoCoreCommands
{
    MEASURE_VOLT,
    MEASURE_TEMP
}

impl std::fmt::Display for VideoCoreCommands
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        match self
        {
            VideoCoreCommands::MEASURE_TEMP => write!(f, "measure_temp"),
            VideoCoreCommands::MEASURE_VOLT => write!(f, "measure_volt")
        }    
    }
}

pub fn VCGENCMD(cmd:VideoCoreCommands,config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "vcgencmd",
        Some(vec![cmd.to_string()]),
        None,
        None,
        config
    )
}