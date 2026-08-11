use super::*;
use std::fmt::{Display,Formatter,Result};
use tracing::error;

#[derive(PartialEq)]
#[derive(Debug)]
#[derive(Clone)]
pub struct POSIXPermissions
{
    pub r:bool,
    pub w:bool,
    pub x:bool
}
#[derive(PartialEq)]
#[derive(Debug)]
pub struct FileSystemPermissions
{
    pub user:Option<POSIXPermissions>,
    pub group:Option<POSIXPermissions>,
    pub others:Option<POSIXPermissions>
}

pub enum OSUser
{
    ID(u32),
    Name(String),
    Empty
}

pub type OSGroup = OSUser;

pub enum StatFormat<'a>
{
    PermissionsOctal,
    PermissionReadable,
    NumBlocks,
    BlockSize,
    SelinuxContext,
    DevNum,
    DevNumHex,
    MajorDevNum,
    MinorDevNum,
    ModeHex,
    FileType,
    Gid,
    GroupName,
    NumHardLinks,
    Inode,
    Mountpoint,
    Filename,
    DefFilename,
    Size,
    DevTypeDec,
    DevTypeHex,
    MajorDevTypeDec,
    MinorDevTypeDec,
    MajorDevTypeHex,
    MinorDevTypeHex,
    Uid,
    User,
    TimeCreated,
    TimeCreatedEpoch,
    TimeLastAccess,
    TimeLastAccessEpoch,
    TimeLastEdit,
    TimeLastEditEpoch,
    TimeLastStatusChange,
    TimeLastStatusChangeEpoch,
    Filler(&'a str)
}

impl<'a> std::fmt::Display for StatFormat<'a>
{
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result 
    {
        match self 
        {
            StatFormat::PermissionsOctal => write!(f,"%a"),
            StatFormat::PermissionReadable => write!(f,"%A"),
            StatFormat::NumBlocks => write!(f,"%b"),
            StatFormat::BlockSize => write!(f,"%B"),
            StatFormat::SelinuxContext => write!(f,"%C"),
            StatFormat::DevNum => write!(f,"%d"),
            StatFormat::DevNumHex => write!(f,"%D"),
            StatFormat::MajorDevNum => write!(f,"%Hd"),
            StatFormat::MinorDevNum => write!(f,"%Ld"),
            StatFormat::ModeHex => write!(f,"%f"),
            StatFormat::FileType => write!(f,"%F"),
            StatFormat::Gid => write!(f,"%g"),
            StatFormat::GroupName => write!(f,"%G"),
            StatFormat::NumHardLinks => write!(f,"%h"),
            StatFormat::Inode => write!(f,"%i"),
            StatFormat::Mountpoint => write!(f,"%m"),
            StatFormat::Filename => write!(f,"%n"),
            StatFormat::DefFilename => write!(f,"%N"),
            StatFormat::Size => write!(f,"%s"),
            StatFormat::DevTypeDec => write!(f,"%r"),
            StatFormat::DevTypeHex => write!(f,"%R"),
            StatFormat::MajorDevTypeDec => write!(f,"%Hr"),
            StatFormat::MinorDevTypeDec => write!(f,"%Lr"),
            StatFormat::MajorDevTypeHex => write!(f,"%t"),
            StatFormat::MinorDevTypeHex => write!(f,"%T"),
            StatFormat::Uid => write!(f,"%u"),
            StatFormat::User => write!(f,"%U"),
            StatFormat::TimeCreated => write!(f,"%w"),
            StatFormat::TimeCreatedEpoch => write!(f,"%W"),
            StatFormat::TimeLastAccess => write!(f,"%x"),
            StatFormat::TimeLastAccessEpoch => write!(f,"%X"),
            StatFormat::TimeLastEdit => write!(f,"%y"),
            StatFormat::TimeLastEditEpoch => write!(f,"%Y"),
            StatFormat::TimeLastStatusChange => write!(f,"%z"),
            StatFormat::TimeLastStatusChangeEpoch => write!(f,"%Z"),
            StatFormat::Filler(s) => write!(f,"{s}")
        }
    }
}


impl POSIXPermissions
{
    pub fn from_octal(permission:u8) -> POSIXPermissions
    {
        if permission>7 { panic!("POSIX file system permissions must be between 0 and 7"); }

        let r = (permission & 0b100) != 0;
        let w = (permission & 0b010) != 0;
        let x = (permission & 0b001) != 0;

        POSIXPermissions{r,w,x}
    }

    pub fn from_string(permission:&String) -> POSIXPermissions
    {
        let perm_characters:Vec<char> = "rwx".chars().collect();
        let mut idx = 0;
        let mut perm = POSIXPermissions{r:false, w:false, x:false};

        for c in permission.chars()
        {
            let mut parsed = false;
            while idx<perm_characters.len()
            {
                if c == '-' 
                { 
                    parsed=true;
                }
                else if c==perm_characters[idx]
                {
                    parsed=true;
                    match c
                    {
                        'r' => perm.r=true,
                        'w' => perm.w=true,
                        'x' => perm.x=true,
                        _ => break //I have to add this but it will never get here
                    }
                }
               
                idx+=1;

                if parsed { break; }
                
            }

            if !parsed { error!("Unrecognised character `{c}` in `{permission}`. Make sure the order of the permissions in 'rwx'"); }
        }


        return perm;
    }
    
    pub fn to_octal(self:&Self) -> u8
    {
       (0b100 * (if self.r {1} else {0})) | (0b10 * (if self.w {1} else {0})) | (0b1 * (if self.x {1} else {0})) 
    }
}

impl Display for POSIXPermissions
{
    fn fmt(&self, f: &mut Formatter<'_>) -> Result 
    {
        let mut perm = String::new();

        if self.r { perm.push('r'); }
        if self.w { perm.push('w'); }
        if self.x { perm.push('x'); }

        write!(f,"{perm}")
    }
}

impl FileSystemPermissions
{
    pub fn for_user(perm:&String) -> FileSystemPermissions
    {
        FileSystemPermissions
        {
            user: Some(POSIXPermissions::from_string(perm)),
            group: None,
            others: None
        }
    }

    pub fn for_group(perm:&String) -> FileSystemPermissions
    {
        FileSystemPermissions
        {
            user: None,
            group: Some(POSIXPermissions::from_string(perm)),
            others: None
        }
    }

    pub fn for_others(perm:&String) -> FileSystemPermissions
    {
        FileSystemPermissions
        {
            user: None,
            group: None,
            others: Some(POSIXPermissions::from_string(perm)),
        }
    }

    pub fn for_all(user:&String,group:&String,others:&String) -> FileSystemPermissions
    {
        FileSystemPermissions::new(
            Some(user),
            Some(group),
            Some(others)
        )
    }

    pub fn new(user:Option<&String>,group:Option<&String>,others:Option<&String>) -> FileSystemPermissions
    {
        FileSystemPermissions
        {
            user: if let Some(u) = user {Some(POSIXPermissions::from_string(u))} else {None},
            group: if let Some(g) = group {Some(POSIXPermissions::from_string(g))} else {None},
            others: if let Some(o) = others {Some(POSIXPermissions::from_string(o))} else {None},
        }
    }

    pub fn same_for_all(perm:&String) -> FileSystemPermissions
    {
        let p = POSIXPermissions::from_string(perm);
        FileSystemPermissions
        {
            user: Some(p.clone()),
            group: Some(p.clone()),
            others: Some(p),
        }
    }

    pub fn from_mode(mode:u32) -> FileSystemPermissions
    {
        let u:u8 = ((mode & 0o700)>>6) as u8;
        let g:u8 = ((mode & 0o70)>>3) as u8;
        let o:u8 = (mode & 0o7) as u8;

        FileSystemPermissions 
        { 
            user: Some(POSIXPermissions::from_octal(u)),
            group: Some(POSIXPermissions::from_octal(g)),
            others: Some(POSIXPermissions::from_octal(o))
        }
    }


}

impl Display for FileSystemPermissions
{
    fn fmt(&self, f: &mut Formatter<'_>) -> Result 
    {

        if (self.user.is_some()) && (self.group.is_some()) && (self.others.is_some())
        {
            let u = self.user.as_ref().unwrap().to_octal();
            let g = self.group.as_ref().unwrap().to_octal();
            let o = self.others.as_ref().unwrap().to_octal();
            return write!(f,"{u}{g}{o}");
        }

        let mut perms:Vec<String> = Vec::new();

        if let Some(u) = &self.user { perms.push(format!("u={u}")); }
        if let Some(g) = &self.group { perms.push(format!("g={g}")); }
        if let Some(o) = &self.others { perms.push(format!("o={o}")); }
        
        write!(f,"{}",perms.join(","))
    }
}

pub fn LS(path:&String,config:CmdConfig) -> CommandLine
{
    return CommandLine::new(
        "ls",
        Some(vec![path.clone()]),
        None,
        None,
        config
    );
}

pub fn Cat<S:AsRef<str>+ToString>(path:Option<S>, config:CmdConfig) -> CommandLine
{
    if let Some(p) = path
    {
       return CommandLine::new(
            "cat",
            Some(vec![p.to_string()]),
            None,
            None,
            config
        );
    }
    else
    {
        if let CmdConfig::Provided {stdin,..} = &config && stdin.is_some()
        {

            return CommandLine::new(
                "cat",
                None,
                None,
                None,
                config
            );

        }

        panic!("Invalid use of `cat`. Either provide a filename OR piped data.");
    }
}

pub fn MV<S1:AsRef<str>+ToString, S2:AsRef<str>+ToString>(src:S1, dst:S2,config:CmdConfig) -> CommandLine
{
    let cmd:&'static str = "mv";

    CommandLine::new(
        cmd,
        Some(vec![src.to_string(),dst.to_string()]),
        Some(Box::new(CommandLine::new(
            cmd,
            Some(vec![dst.to_string(),src.to_string()]),
            None,
            None,
            config.clone()
        ))),
        None,
        config
    )
}

pub fn CP(src:&String, dst:&String,recursive:bool,config:CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();

    if recursive { args.push("-r".to_string()); }

    args.push(src.clone());
    args.push(dst.clone());

    CommandLine::new(
        "cp", 
        Some(args),
        Some(Box::new(
            RM(dst,recursive,false,config.clone())
        )),
        None, 
        config
    )
}

pub fn RM<S:AsRef<str>+ToString>(filename:S,
                recursive:bool,
                revertible:bool,
                config:CmdConfig) -> CommandLine
{
    if revertible
    {
        let mut new_name:String = filename.to_string();
        new_name.push_str(".bkp");

        let mut mv_cmd = MV(filename,new_name.clone(),config.clone());



        mv_cmd.drop = Some(Box::new(move |_:&Pin<&mut CommandLine>|
        {
            let file_to_remove = new_name;
            let cfg = config.clone();

            Box::pin( async move {

                let r = RM(&file_to_remove, recursive, false, cfg).run().await;
                match r
                {
                    Err(e) => error!("Error while executing `rm` cleanup function: {}",e),
                    Ok(_) => ()
                }
            })
        }));

        return mv_cmd;
    }

    let mut args:Vec<String> = Vec::new();

    if recursive {args.push("-rf".to_string());}
    args.push(filename.to_string());

    CommandLine::new(
        "rm",
        Some(args),
        None,
        None,
        config
    )
}

pub fn DD(input_file:&String, output_file:&String,bytes:Option<u32>, count:Option<u32>, config:CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = vec![
        format!("if={input_file}"),
        format!("of={output_file}")
    ];

    if let Some(b) = bytes
    {
        args.push(format!("bs={b}"));
    }

    if let Some(c) = count
    {
        args.push(format!("count={c}"));
    }

    CommandLine::new(
        "dd",
        Some(args),
        None,
        None,
        config
    )
}

pub fn CreateKey(filename:&String,config:CmdConfig) -> CommandLine
{
    DD(&"/dev/urandom".to_string(),filename,Some(32),Some(1),config)
}

pub fn Chmod<S:AsRef<str> + ToString>(permissions:&FileSystemPermissions,
                    old_permissions:Option<&FileSystemPermissions>,
                    filename:S,
                    recursive:bool,
                    config:CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();

    if recursive { args.push("-R".to_string()); }

    args.push(permissions.to_string());
    args.push(filename.to_string());

    CommandLine::new(
        "chmod",
        Some(args),
        match old_permissions
        {
            Some (p) => Some(Box::new(Chmod(p,None,filename,recursive,config.clone()))),
            None => None
        },
        None,
        config
    )
}

fn chown_owner_formatter(u:&OSUser,g:&OSUser) -> String
{
    let mut fmt:String = String::new();

    match u
    {
        OSUser::ID(id) => fmt.push_str(format!("{id}").as_str()),
        OSUser::Name(n) => fmt.push_str(format!("{n}").as_str()),
        OSUser::Empty => (),
    }

    match g
    {
        OSUser::ID(id) => fmt.push_str(format!(":{id}").as_str()),
        OSUser::Name(n) => fmt.push_str(format!(":{n}").as_str()),
        OSUser::Empty => (),
    }

    return fmt;
}

pub fn Chown(
                    user:&OSUser,
                    group:&OSUser,
                    old_user:&OSUser,
                    old_group:&OSUser,
                    filename:&str,
                    recursive:bool,
                    config:CmdConfig
                ) -> CommandLine
{
    let new_owner = chown_owner_formatter(user, group);
    let old_owner = chown_owner_formatter(old_user, old_group);

    if new_owner.len() == 0 { panic!("You must specify either a new user or a new group"); }

    let mut args:Vec<String> = Vec::new();

    if recursive { args.push("-R".to_string()); }

    args.push(new_owner);
    args.push(filename.to_string());

    CommandLine::new(
        "chown",
        Some(args),
        if old_owner.len()>0
        {
            Some(Box::new(Chown(
                old_user, old_group,
                &OSUser::Empty, &OSUser::Empty,
                filename,
                recursive,
                config.clone()
            )))
        }
        else { None },
        None,
        config
    )
}

pub fn Mkdir(path:&String,permissions:Option<FileSystemPermissions>,config:CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();

    if let Some(p) = permissions
    {
        args.push("-m".to_string());
        args.push(p.to_string());
    }

    args.push(path.clone());


    CommandLine::new(
        "mkdir",
        Some(args),
        {
            Some(Box::new(
                RM(path,true,false,config.clone())
            ))
        },
        None,
        config
    )
}


pub fn Touch<S:AsRef<str> + ToString>(filename:S,config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "touch",
        Some(vec![filename.to_string()]),
        Some(Box::new(RM(
            filename,
            false,
            false,
            config.clone()
        ))),
        None, 
        config)
}

pub fn Stat<'c,S:AsRef<str>+ToString>(filename:S,format:Option<Vec<StatFormat<'c>>>,config:CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();

    if let Some(fmt) = format
    {
        args.push("--format".to_string());
        args.extend(fmt.iter().map(|x|x.to_string()).collect::<Vec<String>>());
    }

    args.push(filename.to_string());

    CommandLine::new(
        "stat",
        Some(args),
        None,
        None,
        config
    )
}

pub fn Readlink(path:&String,config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "readlink",
        Some(vec![path.clone()]),
        None,
        None,
        config
    )
}

pub fn MD5Sum(path:&String,config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "md5sum",
        Some(vec![path.clone()]),
        None,
        None,
        config
    )
}

pub fn Truncate(filename:&String,size:usize,config:CmdConfig)  -> CommandLine
{
    CommandLine::new(
        "truncate",
        Some(vec!["-s".to_string(),format!("{size}"),filename.clone()]),
        None,
        None,
        config
    )
}

pub fn Tee<S:AsRef<str>+ToString>(filename:S,append:bool, config:CmdConfig)  -> CommandLine
{
    let mut args:Vec<String> = Vec::new();
    
    if config.stdin_data().is_none()
    {
        panic!("Tee must have stdin data to be provided.");
    }
    
    if append { args.push("-a".to_string()); }
    
    args.push(filename.to_string());
    
    CommandLine::new(
        "tee",
        Some(args),
        None,
        None,
        config
    )
}

pub fn UserID(username:&str,config:CmdConfig)  -> CommandLine
{
    let args = vec!["-u",username].iter().map(|x|x.to_string()).collect::<Vec<String>>();
    
    CommandLine::new(
        "id",
        Some(args),
        None,
        None,
        config
    )
}

// mod tests
// {
//     use super::*;
//     use std::path::Path;

//     fn touch_file(filename:&'static str)
//     {
//         Touch(&filename.to_string(),None).run();
//     }

//     #[test]
//     fn ls_test()
//     {
//         let directory = "/".to_string();
//         let ls_test = LS(&directory,None);
//         let ls_out = ls_test.run();

//         assert!(ls_out.is_some());

//         let result = ls_out.unwrap();

//         let output = result.stdout;

//         assert_eq!(result.status_code, 0);

//         let matches:Vec<&str> = output.matches("dev").collect();

//         assert_eq!(matches,vec!["dev"]);
//     }



//     #[test]
//     fn cat_test()
//     {
//         let cat_test = Cat(Some(&"src/main.rs".to_string()),None);
//         let cat_out  = cat_test.run();

//         assert!(cat_out.is_some());

//         let result = cat_out.unwrap();

//         let output = result.stdout;

//         assert_eq!(result.status_code, 0);

//         let matches:Vec<&str> = output.matches("fn main").collect();

//         assert_eq!(matches,vec!["fn main"]);
//     }

//     #[test]
//     fn cat_piped()
//     {
//         let directory = "/".to_string();
//         let ls_test = LS(&directory,None);
//         let ls_out = ls_test.run();

//         assert!(ls_out.is_some());

//         let result = ls_out.unwrap();

//         let piped_stdin = &result.stdout[..];

//         let cat_pipe_config = CmdConfig::new(
//             false,
//             true,
//             Some(piped_stdin),
//             None
//         );


//         let cat_pipe_test = Cat(None, Some(&cat_pipe_config));

//         let cat_pipe_out = cat_pipe_test.run();

//         assert!(cat_pipe_out.is_some());

//         let cat_pipe_result = cat_pipe_out.unwrap();

//         assert_eq!(cat_pipe_result.status_code,0);

//         assert_eq!(cat_pipe_result.stdout,result.stdout);
//     }


//     #[test]
//     fn POSIXPermissions()
//     {
//         assert_eq!(POSIXPermissions::from_octal(0o4), POSIXPermissions{r:true,w:false,x:false});
//         assert_eq!(POSIXPermissions::from_octal(0o2), POSIXPermissions{r:false,w:true,x:false});
//         assert_eq!(POSIXPermissions::from_octal(0o1), POSIXPermissions{r:false,w:false,x:true});
//         assert_eq!(POSIXPermissions::from_octal(0o0), POSIXPermissions{r:false,w:false,x:false});

//         assert_eq!(POSIXPermissions::from_octal(0o6), POSIXPermissions{r:true,w:true,x:false});
//         assert_eq!(POSIXPermissions::from_octal(0o5), POSIXPermissions{r:true,w:false,x:true});
//         assert_eq!(POSIXPermissions::from_octal(0o3), POSIXPermissions{r:false,w:true,x:true});
//         assert_eq!(POSIXPermissions::from_octal(0o7), POSIXPermissions{r:true,w:true,x:true});
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsFail()
//     {
//         POSIXPermissions::from_octal(0o10);
//     }

//     #[test]
//     fn POSIXPermissionsString()
//     {
//         assert_eq!(POSIXPermissions::from_string(&"r".to_string()), POSIXPermissions{r:true,w:false,x:false});
//         assert_eq!(POSIXPermissions::from_string(&"r-".to_string()), POSIXPermissions{r:true,w:false,x:false});
//         assert_eq!(POSIXPermissions::from_string(&"r--".to_string()), POSIXPermissions{r:true,w:false,x:false});
        
//         assert_eq!(POSIXPermissions::from_string(&"w".to_string()), POSIXPermissions{r:false,w:true,x:false});
//         assert_eq!(POSIXPermissions::from_string(&"-w".to_string()), POSIXPermissions{r:false,w:true,x:false});
//         assert_eq!(POSIXPermissions::from_string(&"-w-".to_string()), POSIXPermissions{r:false,w:true,x:false});
        
//         assert_eq!(POSIXPermissions::from_string(&"x".to_string()), POSIXPermissions{r:false,w:false,x:true});
//         assert_eq!(POSIXPermissions::from_string(&"-x".to_string()), POSIXPermissions{r:false,w:false,x:true});
//         assert_eq!(POSIXPermissions::from_string(&"--x".to_string()), POSIXPermissions{r:false,w:false,x:true});
        
//         assert_eq!(POSIXPermissions::from_string(&"".to_string()), POSIXPermissions{r:false,w:false,x:false});
//         assert_eq!(POSIXPermissions::from_string(&"-".to_string()), POSIXPermissions{r:false,w:false,x:false});
//         assert_eq!(POSIXPermissions::from_string(&"--".to_string()), POSIXPermissions{r:false,w:false,x:false});
//         assert_eq!(POSIXPermissions::from_string(&"---".to_string()), POSIXPermissions{r:false,w:false,x:false});

//         assert_eq!(POSIXPermissions::from_string(&"rw".to_string()), POSIXPermissions{r:true,w:true,x:false});
//         assert_eq!(POSIXPermissions::from_string(&"rw-".to_string()), POSIXPermissions{r:true,w:true,x:false});

//         assert_eq!(POSIXPermissions::from_string(&"rx".to_string()), POSIXPermissions{r:true,w:false,x:true});
//         assert_eq!(POSIXPermissions::from_string(&"r-x".to_string()), POSIXPermissions{r:true,w:false,x:true});

//         assert_eq!(POSIXPermissions::from_string(&"rwx".to_string()), POSIXPermissions{r:true,w:true,x:true});
//     }

//     #[test]
//     fn FileSystemPermissions()
//     {
//         let p = FileSystemPermissions::for_user(&"r".to_string());
//         assert_eq!(format!("{p}"),"u=r");

//         let p = FileSystemPermissions::for_user(&"w".to_string());
//         assert_eq!(format!("{p}"),"u=w");

//         let p = FileSystemPermissions::for_user(&"x".to_string());
//         assert_eq!(format!("{p}"),"u=x");

//         let p = FileSystemPermissions::for_user(&"rw".to_string());
//         assert_eq!(format!("{p}"),"u=rw");

//         let p = FileSystemPermissions::for_user(&"rx".to_string());
//         assert_eq!(format!("{p}"),"u=rx");

//         let p = FileSystemPermissions::for_user(&"wx".to_string());
//         assert_eq!(format!("{p}"),"u=wx");

//         let p = FileSystemPermissions::for_user(&"rwx".to_string());
//         assert_eq!(format!("{p}"),"u=rwx");


//         let p = FileSystemPermissions::for_group(&"r".to_string());
//         assert_eq!(format!("{p}"),"g=r");

//         let p = FileSystemPermissions::for_group(&"w".to_string());
//         assert_eq!(format!("{p}"),"g=w");

//         let p = FileSystemPermissions::for_group(&"x".to_string());
//         assert_eq!(format!("{p}"),"g=x");

//         let p = FileSystemPermissions::for_group(&"rw".to_string());
//         assert_eq!(format!("{p}"),"g=rw");

//         let p = FileSystemPermissions::for_group(&"rx".to_string());
//         assert_eq!(format!("{p}"),"g=rx");

//         let p = FileSystemPermissions::for_group(&"wx".to_string());
//         assert_eq!(format!("{p}"),"g=wx");

//         let p = FileSystemPermissions::for_group(&"rwx".to_string());
//         assert_eq!(format!("{p}"),"g=rwx");


//         let p = FileSystemPermissions::for_others(&"r".to_string());
//         assert_eq!(format!("{p}"),"o=r");

//         let p = FileSystemPermissions::for_others(&"w".to_string());
//         assert_eq!(format!("{p}"),"o=w");

//         let p = FileSystemPermissions::for_others(&"x".to_string());
//         assert_eq!(format!("{p}"),"o=x");

//         let p = FileSystemPermissions::for_others(&"rw".to_string());
//         assert_eq!(format!("{p}"),"o=rw");

//         let p = FileSystemPermissions::for_others(&"rx".to_string());
//         assert_eq!(format!("{p}"),"o=rx");

//         let p = FileSystemPermissions::for_others(&"wx".to_string());
//         assert_eq!(format!("{p}"),"o=wx");

//         let p = FileSystemPermissions::for_others(&"rwx".to_string());
//         assert_eq!(format!("{p}"),"o=rwx");


//         let p = FileSystemPermissions::same_for_all(&"r".to_string());
//         assert_eq!(format!("{p}"),"444");

//         let p = FileSystemPermissions::same_for_all(&"w".to_string());
//         assert_eq!(format!("{p}"),"222");

//         let p = FileSystemPermissions::same_for_all(&"x".to_string());
//         assert_eq!(format!("{p}"),"111");

//         let p = FileSystemPermissions::same_for_all(&"rw".to_string());
//         assert_eq!(format!("{p}"),"666");

//         let p = FileSystemPermissions::same_for_all(&"rx".to_string());
//         assert_eq!(format!("{p}"),"555");

//         let p = FileSystemPermissions::same_for_all(&"wx".to_string());
//         assert_eq!(format!("{p}"),"333");

//         let p = FileSystemPermissions::same_for_all(&"rwx".to_string());
//         assert_eq!(format!("{p}"),"777");


//         let perm1 = Some(&"r".to_string());
//         let perm2 = Some(&"rwx".to_string());
//         let perm3 = Some(&"wx".to_string());

//         let p = FileSystemPermissions::new(perm1,perm2,None);
//         assert_eq!(format!("{p}"),"u=r,g=rwx");

//         let p = FileSystemPermissions::new(perm2,None,perm1);
//         assert_eq!(format!("{p}"),"u=rwx,o=r");

//         let p = FileSystemPermissions::new(None,perm1,perm2);
//         assert_eq!(format!("{p}"),"g=r,o=rwx");

//         let p = FileSystemPermissions::new(None,perm1,perm2);
//         assert_eq!(format!("{p}"),"g=r,o=rwx");


//         let p = FileSystemPermissions::for_all(perm1.unwrap(),perm2.unwrap(),perm3.unwrap());
//         assert_eq!(format!("{p}"),"473");

//         let p = FileSystemPermissions::for_all(perm2.unwrap(),perm1.unwrap(),perm3.unwrap());
//         assert_eq!(format!("{p}"),"743");

//         let p = FileSystemPermissions::for_all(perm3.unwrap(),perm1.unwrap(),perm2.unwrap());
//         assert_eq!(format!("{p}"),"347");


//         let p = FileSystemPermissions::from_mode(0o100644);
//         assert_eq!(format!("{p}"),"644");


        
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrong_r()
//     {
//         POSIXPermissions::from_string(&"-r".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrong__r()
//     {
//         POSIXPermissions::from_string(&"--r".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrong__w()
//     {
//         POSIXPermissions::from_string(&"--w".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrongw__()
//     {
//         POSIXPermissions::from_string(&"w--".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrongx__()
//     {
//         POSIXPermissions::from_string(&"x--".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrongx_()
//     {
//         POSIXPermissions::from_string(&"x-".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrong_rw()
//     {
//         POSIXPermissions::from_string(&"-rw".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrongrx_()
//     {
//         POSIXPermissions::from_string(&"rx-".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrong_rx()
//     {
//         POSIXPermissions::from_string(&"-rx".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrong_wrx()
//     {
//         POSIXPermissions::from_string(&"wrx".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrong_wxr()
//     {
//         POSIXPermissions::from_string(&"wxr".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrong_rxw()
//     {
//         POSIXPermissions::from_string(&"rxw".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrong_xwr()
//     {
//         POSIXPermissions::from_string(&"xwr".to_string());
//     }

//     #[test]
//     #[should_panic]
//     fn POSIXPermissionsStringWrong_xrw()
//     {
//         POSIXPermissions::from_string(&"xrw".to_string());
//     }


//     fn createkey_setup() -> Option<CommandOutput>
//     {
//         let key_fname = "test.key".to_string();
//         CreateKey(&key_fname,None).run()
//     }

//     #[test]
//     fn CreateKey_test_include_DD()
//     {
//         let output = createkey_setup();

//         assert!(output.is_some());

//         let result = output.unwrap();

//         assert_eq!(result.status_code,0);

//         let key_fn = Path::new("test.key");

//         assert!(key_fn.exists());
//     }

    
//     fn RM_soft_test()
//     {
//         let key_fn = Path::new("test.key");

//         if !key_fn.exists() { createkey_setup(); }

//         assert!(key_fn.exists());

//         let rm = RM(&key_fn.as_os_str().to_str().unwrap().to_string(),false,true,None);
//         rm.run();
        
//         let key_fn_backup = Path::new("test.key.bkp");

//         assert!(key_fn_backup.exists());

//         drop(rm);

//         assert!(!key_fn_backup.exists());
//     }


//     fn RM_test()
//     {
//         let key_fn = Path::new("test.key");

//         if !key_fn.exists() { createkey_setup(); }

//         assert!(key_fn.exists());

//         let rm = RM(&key_fn.as_os_str().to_str().unwrap().to_string(),false,false,None);
//         rm.run();

//         let key_fn_backup = Path::new("test.key.bkp");

//         assert!(!key_fn_backup.exists());
//         assert!(!key_fn.exists());

//         drop(rm);

//         assert!(!key_fn.exists());
//     }

//     #[test]
//     fn RM_tests()
//     {
//         RM_soft_test();
//         RM_test();
//     }

//     #[test]
//     fn Chmod_test()
//     {
//         let fname = "chmod.test";

//         touch_file(fname);

//         let fname_string = fname.to_string();

//         let fname_path = Path::new(&fname_string);
//         assert!(fname_path.exists());

//         let permissions = FileSystemPermissions::from_mode(0o321);

//         let cmd = Chmod(&permissions,None,&fname_string,false,None);
//         cmd.run();


//         let mode = fs::metadata(fname_path).unwrap().permissions().mode();

//         assert_eq!(mode,0o100321);

//         RM(&fname_string,false,false,None).run();
//         assert!(!fname_path.exists());
//     }

//     #[test]
//     fn Mkdir_test()
//     {
//         let dir1 = "mkdir_test".to_string();
//         let dir2= format!("{dir1}/a");
//         let dir3 = format!("{dir2}/b");

//         let path1 = Path::new(&dir1);
//         let path2= Path::new(&dir2);
//         let path3= Path::new(&dir3);

//         assert!(!path1.exists());
//         assert!(!path2.exists());
//         assert!(!path3.exists());

//         Mkdir(&dir1,None,None).run();
//         Mkdir(&dir2,None,None).run();
//         Mkdir(&dir3,Some(FileSystemPermissions::same_for_all(&"rx".to_string())),None).run();

//         assert!(path1.exists());
//         assert!(path2.exists());
//         assert!(path3.exists());

//         let mode = fs::metadata(path3).unwrap().permissions().mode();

//         let perm = FileSystemPermissions::from_mode(mode);

//         assert_eq!(perm,FileSystemPermissions{
//             user:Some(POSIXPermissions{r:true,w:false,x:true}),
//             group:Some(POSIXPermissions{r:true,w:false,x:true}),
//             others:Some(POSIXPermissions{r:true,w:false,x:true}),
//         });

//         RM(&dir1,true,false,None).run();

//         assert!(!path1.exists());
//         assert!(!path2.exists());
//         assert!(!path3.exists());
//     }
    
// }