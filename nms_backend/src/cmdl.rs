
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
use std::process::{Command,Stdio};
use std::io::Write;

type Destructor<'a,T> = Box<dyn Fn(&T) + 'a>;

trait CmdFlag<T>
{
    fn flag(value:&T) -> &'static str;
}

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

#[derive(Debug)]
pub struct CommandOutput
{
    pub status_code:i32,
    pub stdout:String,
    pub stderr:String
}

pub trait Executable
{
    fn run(self:&Self) -> Option<CommandOutput>;
    fn execute(self:&Self,revert:bool) -> Option<CommandOutput>;
}

trait ExecutableInternal
{
    fn execute_cmd(self:&Self)  -> Option<CommandOutput>;
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
}

impl<'a,'b> ExecutableInternal for CommandLine<'a,'b>
{
    fn execute_cmd(self:&Self)  -> Option<CommandOutput>
    {
        let mut cmd;

        let sudo:bool = {
            if let Some(config) = &self.config { config.sudo } else {false}
        };

        let strict:bool = {
            if let Some(config) = &self.config { config.strict } else {true}
        };

        let stdin_data:Option<&'a str> = {
            if let Some(config) = &self.config { config.stdin } else {None}
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
                status_code: if strict { o.status.code().unwrap() } else { 0 },
                stdout: String::from_utf8_lossy(&o.stdout).to_string(),
                stderr: String::from_utf8_lossy(&o.stderr).to_string()
            }),
            Err(e) => if strict {panic!("Error while running {}: {}",self.command,e)} else {None}
        }
    }
}




