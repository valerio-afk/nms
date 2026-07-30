pub mod coreutils;
pub mod others;
pub mod compression;
pub mod acpi;
pub mod systemd;
pub mod utils;
pub mod rpi;
pub mod net;
pub mod package_mngt;
pub mod passwd;
pub mod docker;
pub mod zfs;
pub mod notify;

use tokio;
use tokio::process::{Child, Command};
use std::process::Stdio;
use std::fmt::{self, Display, Formatter};
use core::error::Error;
use std::pin::Pin;
use tokio::io::AsyncWriteExt;

#[derive(Debug)]
pub enum CommandError
{
    SpawnError(&'static str, std::io::Error),
    StdinError(&'static str),
    StdinWriteError(&'static str, std::io::Error),
    ExecutionError(&'static str,std::io::Error),
}

impl Display for CommandError
{
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result
    {
        match self
        {
            CommandError::SpawnError(cmd, e) => write!(f, "Unable to spawn `{}`: {}", cmd, e),
            CommandError::StdinError(cmd) => write!(f, "Unable to obtain stdin for `{}`", cmd),
            CommandError::StdinWriteError(cmd, e) => write!(f, "Unable to write into stdin of `{}`: {}", cmd, e),
            CommandError::ExecutionError(cmd, e) => write!(f, "Unable to execute `{}`: {}", cmd, e),
        }
    }
}
impl Error for CommandError {}

type DestructorFuture = Pin<Box<dyn Future<Output = ()> + Send>>;
type Destructor<T> = Box<dyn Fn(&Pin<&mut T>) -> DestructorFuture + Send>;

trait CmdFlag<T>
{
    fn flag(value:&T) -> &'static str;
}

const CMD_CONFIG_DEFAULT:CmdConfig = CmdConfig::Provided{
    sudo: true,
    strict:true,
    stdin:None,
    cwd:None
};


pub struct CommandLine
{
    command:&'static str,
    args:Option<Vec<String>>,
    revert_cmd:Option<Box<CommandLine>>,
    config: CmdConfig,
    drop: Option<Destructor<Self>>
}

#[derive(Clone,Debug)]
pub enum CmdConfig
{
    Provided {
        sudo: bool,
        strict: bool,
        stdin: Option<Vec<u8>>,
        cwd: Option<String>
    },
    Empty
}

impl CmdConfig
{

    pub fn is_provided(&self)-> bool
    {
        if let CmdConfig::Provided{..} = self {true} else {false}
    }

    pub fn is_empty(&self)-> bool
    {
        !self.is_provided()
    }
    pub fn is_sudo(&self) -> bool
    {
        match &self
        {
            CmdConfig::Provided {sudo,..} => *sudo,
            CmdConfig::Empty => false
        }
    }

    pub fn set_sudo(&mut self, new_sudo: bool)
    {
        match self
        {
            CmdConfig::Provided {sudo,..} => *sudo=new_sudo,
            CmdConfig::Empty => {
                *self = CmdConfig::Provided {
                    sudo: new_sudo,
                    strict: true,
                    stdin: None,
                    cwd: None,
                };
            }
        }
    }

    pub fn is_strict(&self) -> bool
    {
        match &self
        {
            CmdConfig::Provided {strict,..} => *strict,
            CmdConfig::Empty => false
        }
    }

    pub fn stdin_data(&self) -> Option<&[u8]>
    {
        match &self
        {
            CmdConfig::Provided {stdin,..} => {
                if let Some(data) = stdin
                {
                    Some(data)
                }
                else { None }
            },
            CmdConfig::Empty => None
        }
    }

    pub fn take_data(&mut self) -> Option<Vec<u8>>
    {
        match self
        {
            CmdConfig::Provided {stdin,..} => {stdin.take()},
            CmdConfig::Empty => None
        }
    }

    pub fn cwd(&self) -> Option<&String>
    {
        match &self
        {
            CmdConfig::Provided {cwd,..} => {
                if let Some(dir) = cwd
                {
                    Some(dir)
                }
                else { None }
            },
            CmdConfig::Empty => None
        }
    }
}

impl Default for CmdConfig
{
    fn default() -> CmdConfig
    {
        CMD_CONFIG_DEFAULT.clone()
    }
}

#[derive(Debug)]
pub struct ExitCodeError
{
    exit_code:i32,
    stderr: String
}

impl fmt::Display for ExitCodeError
{
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result 
    {
        write!(f,"{} ({})",self.stderr,self.exit_code)
    }
}

impl std::error::Error for ExitCodeError {}

#[derive(Debug)]
pub struct CommandOutput
{
    pub exit_code:i32,
    pub stdout:String,
    pub stderr:String
}

impl CommandOutput
{
    pub fn check_status(self, code:i32 ) -> Result<Self,ExitCodeError>
    {
        if self.exit_code == code {Ok(self)}
        else {Err(
            ExitCodeError { exit_code: self.exit_code, stderr: self.stderr.to_string() }
        )}
    }

    pub fn is_success(self) -> Result<Self,ExitCodeError>
    {
        self.check_status(0)
    }
}


pub trait Executable
{
    fn run(self) -> impl Future<Output = Result<Option<CommandOutput>,CommandError>> + Send;
    fn spawn(self) -> Result<Child,CommandError>;
    fn execute(self,revert:bool) -> impl Future<Output = Result<Option<CommandOutput>,CommandError>> + Send;

}

trait ExecutableInternal
{
    fn execute_cmd(self)  -> impl Future<Output = Result<CommandOutput,CommandError>> + Send;
    fn spawn_cmd(self) -> Result<Child,CommandError>;
    fn parse_cmd(&self) -> Command;
}

impl CmdConfig
{
    pub fn new(sudo:bool, strict:bool, stdin:Option<&[u8]>,cwd:Option<String>) -> CmdConfig
    {
        CmdConfig::Provided{
            sudo,
            strict,
            stdin: match stdin
            {
                Some(stdin) => Some(stdin.to_vec()),
                None => None
            },
            cwd
        }
    }

}

impl CommandLine
{
    pub fn new(command:&'static str,
               args:Option<Vec<String>>, 
               revert_cmd:Option<Box<CommandLine>>,
               drop:Option<Destructor<CommandLine>>,
               config:CmdConfig) -> CommandLine
    {
        CommandLine{
            command,
            args,
            revert_cmd,
            config,
            drop
        }
    }

    pub fn as_sudo(&mut self)
    {
        self.config.set_sudo(true);
    }

    pub fn take_revert_cmd(&mut self) -> Option<Box<CommandLine>>
    {
        self.revert_cmd.take()
    }
}

impl Drop for CommandLine
{
    fn drop(&mut self)
    {
        if let Some(callback) = self.drop.take()
        {
            tokio::spawn(callback(&Pin::new(self)));
        }
    }
}

impl Executable for CommandLine
{
    async fn run(self)-> Result<Option<CommandOutput>,CommandError>
    {
        return self.execute(false).await
    }

    async fn execute(mut self, revert:bool) ->  Result<Option<CommandOutput>,CommandError>
    {

        if !revert
        {
            Ok(Some(self.execute_cmd().await?))
        }
        else
        {
            match self.revert_cmd.take()
            {
                Some(cmd) => {
                    Ok(Some(cmd.execute_cmd().await?))
                },
                None => Ok(None)
            }
        }
    }

    fn spawn(self) -> Result<Child,CommandError>
    {
        self.spawn_cmd()
    }
}

impl ExecutableInternal for CommandLine
{

    fn parse_cmd(&self) -> Command
    {
        let mut cmd;

        if self.config.is_sudo()
        {
            cmd = Command::new("sudo");
            cmd.arg(self.command);
        }
        else { cmd = Command::new(self.command); }
        
        if let Some(args) = &self.args
        {
            cmd.args(args);
        }

        if let Some(path) = self.config.cwd()
        {
            cmd.current_dir(path);
        }


        return cmd;
    }

    fn spawn_cmd(self) -> Result<Child,CommandError>
    {
  
        let mut cmd = self.parse_cmd();

        cmd.stdin(Stdio::piped())
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .spawn()
                    .map_err(|e| CommandError::SpawnError(self.command, e))

    }

    async fn execute_cmd(mut self)  -> Result<CommandOutput, CommandError>
    {

        let strict:bool = self.config.is_strict();

        let stdin_data:Option<Vec<u8>> = self.config.take_data();

        let cmd = self.command;

        let output= match stdin_data
        {
            None => self.parse_cmd().output().await,
            Some(data) =>
                {
                    let data_slice: &[u8] = &data;
                    let mut child = self.spawn_cmd()?;

                    let mut stdin = child.stdin.take().ok_or(CommandError::StdinError(cmd))?;
                    stdin.write_all(data_slice).await.map_err(|e| CommandError::StdinWriteError(cmd, e))?;
                    drop(stdin);

                    child.wait_with_output().await
                }
        }.map_err(|e| CommandError::ExecutionError(cmd,e))?;

        Ok(CommandOutput{
            exit_code: if strict { output.status.code().unwrap_or(0) } else { 0 },
            stdout: String::from_utf8_lossy(&output.stdout).to_string(),
            stderr: String::from_utf8_lossy(&output.stderr).to_string()
        })

    }
}

pub struct Transaction
{
    commands: Vec<CommandLine>,
    privileged: bool
}

impl Transaction
{
    pub fn new(commands:Vec<CommandLine>) -> Transaction
    {
        Transaction{commands, privileged: false}
    }

    pub fn new_sudo(commands:Vec<CommandLine>) -> Transaction
    {
        Transaction{commands, privileged: true}
    }

    pub async fn execute(mut self) -> Result<Vec<CommandOutput>,CommandError>
    {
        let mut outputs:Vec<CommandOutput> = Vec::new();
        let mut revert_commands:Vec<Option<Box<CommandLine>>> = Vec::new();
        let mut last_error: Option<CommandError> = None;

        for mut cmd in self.commands.drain(0..)
        {
            revert_commands.push(cmd.take_revert_cmd());

            let output = cmd.run().await;

            match output
            {
                Ok(o) => {
                    match o
                    {
                        Some(r) => outputs.push(r),
                        None => ()
                    }
                }
                Err(e) =>
                    {
                        last_error = Some(e);
                        break;

                    },
            }
        }

        if let Some(e) = last_error
        {
            for revert_cmd in revert_commands.drain(0..).into_iter().rev()
            {
                match revert_cmd
                {
                    Some(cmd) => { let _ = cmd.run().await?; }
                    None => ()
                }
            }

            return Err(e);
        }


        Ok(outputs)
    }
}