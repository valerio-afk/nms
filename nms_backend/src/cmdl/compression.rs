use super::*;


#[derive(PartialEq)]
pub enum CompressionAction
{
    Extract,
    Create
}

pub enum TarCompression
{
    Auto,
    BZIP2,
    XZ,
    GZIP,
}

struct TarArchive;
struct SevenZipArchive;


impl CmdFlag<CompressionAction> for TarArchive 
{
    fn flag(action:&CompressionAction) ->  &'static str
    {
        match action 
        {
            CompressionAction::Create => "c",
            CompressionAction::Extract => "x"
        }
    }
}

impl CmdFlag<CompressionAction> for  SevenZipArchive 
{
    fn flag(action:&CompressionAction) ->  &'static str
    {
        match action 
        {
            CompressionAction::Create => "a",
            CompressionAction::Extract => "e"
        }
    }
}


impl std::fmt::Display for TarCompression 
{
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result 
    {
        match self 
        {
            TarCompression::Auto => write!(f,"a"),
            TarCompression::BZIP2 => write!(f,"j"),
            TarCompression::XZ => write!(f,"J"),
            TarCompression::GZIP => write!(f,"z")
        }
    }
}

pub fn Tar(
            tar_filename:&String,
            path:&String,
            action:CompressionAction,
            compression:TarCompression,
            files:Option<&Vec<&String>>,
            exclude:Option<&Vec<&String>>,
            strip_component:Option<u32>,
            config:CmdConfig
        ) -> CommandLine
{
    let flags = format!("-{}{}f",TarArchive::flag(&action),compression);
    let mut args:Vec<String> = vec![
        flags,
        tar_filename.clone(),
        "-C".to_string(),
        path.clone()
    ];

    if let Some(ex) = exclude
    {
        for pattern in ex
        {
            args.push(format!("--exclude={pattern}"));
        }
    }

    if action == CompressionAction::Extract
    {
        if let Some(strip) = strip_component
        {
            args.push(format!("--strip-components={strip}"));
        }
    }

    if let Some(f) = files
    {
        for fname in f
        {
            args.push((*fname).clone());
        }
    }


    CommandLine::new(
        "tar",
        Some(args),
        None,
        None,
        config
    )

    
}

pub fn Unpack(archive:&String,config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "unp",
        Some(vec!["-U".to_string(), archive.clone()]),
        None,
        None,
        config
    )
}

pub fn Zip(
                    archive:&String,
                    files:&Vec<&String>,
                    recursive:bool,
                    config:CmdConfig
                ) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();

    if recursive
    {
        args.push("-r".to_string());
    }

    args.push(archive.clone());

    for f in files
    {
        args.push((*f).clone());
    }

    CommandLine::new(
        "zip",
        Some(args),
        Some(Box::new(coreutils::RM(archive,false,false, config.clone()))),
        None,
        config
    )
}

pub fn SevenZip(
    archive:&String,
    action:CompressionAction,
    files:Option<&Vec<&String>>,
    compression_level:Option<u32>,
    config:CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = vec![SevenZipArchive::flag(&action).to_string()];

    if let Some(lvl) = compression_level
    {
        if lvl > 9
        {
            panic!("Compression level for 7zip must be between 0-9. Provided: {lvl}");
        }

        if action == CompressionAction::Create
        {
            args.push(format!("-mx={lvl}"));
        }
    }

    args.push(archive.clone());

    if action == CompressionAction::Create
    {
        if let Some(f) = files
        {
            for x in f
            {
                args.push((*x).clone());
            }
        }
    }

    CommandLine::new(
        "7z",
        Some(args),
        None,
        None,
        config
    )
}

pub fn ALS(archive:&String,config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "als",
        Some(vec![archive.clone()]),
        None,
        None,
        config
    )
}