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

use std::process::{Child, Command, Stdio};
use std::io::Write;
use std::fmt;

type Destructor<'a,T> = Box<dyn Fn(&T) + 'a>;

trait CmdFlag<T>
{
    fn flag(value:&T) -> &'static str;
}

const CMD_CONFIG_DEFAULT:CmdConfig<'static> = CmdConfig{
    sudo: true,
    strict:true,
    stdin:None,
    cwd:None
};

pub struct CommandLine<'a,'b>
{
    command:&'a str,
    args:Option<Vec<String>>,
    revert_cmd:Option<Box<CommandLine<'a,'b>>>,
    config: Option<&'b CmdConfig<'a>>,
    drop: Option<Destructor<'b, Self>>
}

pub struct CmdConfig<'a>
{
    sudo: bool,
    strict: bool,
    stdin:Option<&'a str>,
    cwd:Option<String>
}

impl<'a> CmdConfig<'a>
{
    pub fn default() -> Option<&'a CmdConfig<'a>>
    {
        Some(&CMD_CONFIG_DEFAULT)
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
    fn run(self:&Self) -> Option<CommandOutput>;
    fn spawn(self:&Self) -> std::io::Result<Child>;
    fn execute(self:&Self,revert:bool) -> Option<CommandOutput>;

}

trait ExecutableInternal
{
    fn execute_cmd(self:&Self)  -> Option<CommandOutput>;
    fn spawn_cmd(self:&Self) -> std::io::Result<Child>;
    fn parse_cmd(self:&Self) -> Command;
}

impl<'a> CmdConfig<'a>
{
    pub fn new(sudo:bool, strict:bool, stdin:Option<&'a str>,cwd:Option<String>) -> CmdConfig<'a>
    {
        CmdConfig {
            sudo: sudo,
            strict: strict,
            stdin: stdin,
            cwd:cwd
        }
    }

}

impl<'a,'b> CommandLine<'a,'b>
{
    pub fn new(command:&'a str,
               args:Option<Vec<String>>, 
               revert_cmd:Option<Box<CommandLine<'a,'b>>>,
               drop:Option<Destructor<'a, CommandLine<'a,'b>>>,
               config:Option<&'b CmdConfig<'a>>) -> CommandLine<'a,'b>
    {
        CommandLine{
            command,
            args,
            revert_cmd,
            config,
            drop
        }
    }
}

impl Drop for CommandLine<'_,'_>
{
    fn drop(self:&mut Self)
    {
        if let Some(callback) = &self.drop
        {
            callback(self);
        }
        
    }
}

impl Executable for CommandLine<'_,'_>
{


    fn run(self:&Self)->Option<CommandOutput>
    {
        self.execute(false)
    }

    fn execute(self:&Self, revert:bool) -> Option<CommandOutput>
    {
        if !revert
        {
            self.execute_cmd()
        }
        else
        {
            match &self.revert_cmd
            {
                Some(cmd) => cmd.execute_cmd(),
                None => None
            }
        }
    }

    fn spawn(self:&Self) -> std::io::Result<Child>
    {
        self.spawn_cmd()
    }
}

impl<'a,'b> ExecutableInternal for CommandLine<'a,'b>
{

    fn parse_cmd(self:&Self) -> Command
    {
        let mut cmd;

        let sudo:bool = {
            if let Some(config) = &self.config { config.sudo } else {false}
        };

        
        let cwd:&Option<String> = {
            if let Some(config) = &self.config { &config.cwd } else { &None }
        };
        

        if sudo
        {
            cmd = Command::new("sudo");
            cmd.arg(self.command);
        }
        else { cmd = Command::new(self.command); }
        
        if let Some(args) = &self.args
        {
            cmd.args(args);
        }

        if let Some(path) = cwd
        {
            cmd.current_dir(path);
        }

        //tracing::debug!("Command to be executed: {cmd:?}");

        return cmd;
    }

    fn spawn_cmd(self:&Self) -> std::io::Result<Child>
    {
  
        let mut cmd = self.parse_cmd();

        cmd.stdin(Stdio::piped())
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .spawn()

         
    }

    fn execute_cmd(self:&Self)  -> Option<CommandOutput>
    {
        let mut cmd = self.parse_cmd();

        let strict:bool = {
            if let Some(config) = &self.config { config.strict } else {true}
        };

        let stdin_data:Option<&'a str> = {
            if let Some(config) = &self.config { config.stdin } else {None}
        };        

        let output;

        if stdin_data == None
        {
            output = cmd.output();  
        }
        else
        {
            let data:&[u8] = stdin_data.unwrap().as_bytes();
            let mut child = cmd.stdin(Stdio::piped())
                        .stdout(Stdio::piped())
                        .stderr(Stdio::piped())
                        .spawn()
                        .expect("Failed to spawn {self.command}");


            let mut stdin = child.stdin.take().expect("Failed to get stdin for {self.command}");
            stdin.write_all(data).expect("Failed to write the stdin for {self.command}");
            drop(stdin);

            output = child.wait_with_output()
        }

        match output
        {
            Ok(o) => Some(CommandOutput{
                exit_code: if strict { o.status.code().unwrap() } else { 0 },
                stdout: String::from_utf8_lossy(&o.stdout).to_string(),
                stderr: String::from_utf8_lossy(&o.stderr).to_string()
            }),
            Err(e) => if strict {panic!("Error while running {}: {}",self.command,e)} else {None}
        }
    }
}




