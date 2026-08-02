use std::collections::HashMap;
use std::string::ToString;
use strum::Display;

use super::*;

const LSBLK_DEFAULT_PROPERTIES: &[LsblkProperties] = &[
            LsblkProperties::NAME,
            LsblkProperties::MODEL,
            LsblkProperties::SERIAL,
            LsblkProperties::TYPE,
            LsblkProperties::TRAN,
            LsblkProperties::SIZE,
            LsblkProperties::PATH
];  

#[derive(Display, Debug)]
pub enum LsblkProperties
{
    ALIGNMENT,

    #[strum(to_string="ID-LINK")]
    IDLINK,
    ID,

    #[strum(to_string="ID-LINK")]
    DISCALN,
    DAX,

    #[strum(to_string="DISC-GRAN")]
    DISCGRAN,

    #[strum(to_string="DISK-SEQ")]
    DISKSEQ,

    #[strum(to_string="DISC-MAX")]
    DISCMAX,

    #[strum(to_string="DISC-ZERO")]
    DISCZERO,
    FSAVAIL,
    FSROOTS,
    FSSIZE,
    FSTYPE,
    FSUSED,

    #[strum(to_string="FSUSE%")]
    FSUSE_P,
    FSVER,
    GROUP,
    HCTL,
    HOTPLUG,
    KNAME,
    LABEL,

    #[strum(to_string="LOG-SEC")]
    LOGSEC,

    #[strum(to_string="MAJ:MIN")]
    MAJ_MIN,

    #[strum(to_string="MIN-IO")]
    MINIO,
    MODE,
    MODEL,
    MQ,
    NAME,

    #[strum(to_string="OPT-IO")]
    OPTIO,
    OWNER,
    PARTFLAGS,
    PARTLABEL,
    PARTN,
    PARTTYPE,
    PARTTYPENAME,
    PARTUUID,
    PATH,

    #[strum(to_string="PHY-SEC")]
    PHYSEC,
    PKNAME,
    PTTYPE,
    PTUUID,
    RA,
    RAND,
    REV,
    RM,
    RO,
    ROTA,

    #[strum(to_string="RQ-SIZE")]
    RQSIZE,
    SCHED,
    SERIAL,
    SIZE,
    START,
    STATE,
    SUBSYSTEMS,
    MOUNTPOINT,
    MOUNTPOINTS,
    TRAN,
    TYPE,
    UUID,
    VENDOR,
    WSAME,
    WWN,
    ZONED,

    #[strum(to_string="ZONE-SZ")]
    ZONESZ,

    #[strum(to_string="ZONE-WGRAN")]
    ZONEWGRAN,

    #[strum(to_string="ZONE-APP")]
    ZONEAPP,

    #[strum(to_string="ZONE-NR")]
    ZONENR,

    #[strum(to_string="ZONE-OMAX")]
    ZONEOMAX,

    #[strum(to_string="ZONE-AMAX")]
    ZONEAMAX,
}

impl LsblkProperties
{
    pub fn default() -> Option<&'static [LsblkProperties]>
    {
        return Some(LSBLK_DEFAULT_PROPERTIES);
    }
}


pub enum SmartctlTest
{
    Offline,
    Short,
    Long,
    Conveyance,
}

impl std::fmt::Display for SmartctlTest
{
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result 
    {
        match self 
        {
            SmartctlTest::Offline => write!(f,"offline"),
            SmartctlTest::Short => write!(f,"short"),
            SmartctlTest::Long => write!(f,"long"),
            SmartctlTest::Conveyance  => write!(f,"conveyance"),
        }
    }
}
pub enum SmartctlActions
{
    List,
    Test(SmartctlTest)
}

impl std::fmt::Display for SmartctlActions
{
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result 
    {
        match self 
        {
            SmartctlActions::List => write!(f,"-ja"),
            SmartctlActions::Test(_) => write!(f,"-t")
        }
    }
}

pub fn LSBLK(
    properties:Option<&[LsblkProperties]>,
    dev_path:Option<&String>,
    config:CmdConfig
) -> CommandLine
{
    let mut args = vec![
        "-J".to_string(),
        "-b".to_string()
    ];

    if let Some(prop) = properties
    {
        args.push("-o".to_string());
        args.push(
            prop.iter().map(|x:&LsblkProperties| x.to_string()).collect::<Vec<String>>().join(",")
        );
    }

    if let Some(p) = dev_path
    {
        args.push(p.to_string())
    }

    CommandLine::new(
        "lsblk",
        Some(args),
        None,
        None,
        config
    )
}

pub fn LSCPU(config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "lscpu",
        None,
        None,
        None,
        config
    )
}

pub fn Find(
    path:String,
    name:Option<String>,
    tests:Option<&HashMap<String,String>>,
    exec:Option<Vec<String>>,
    single_exec:bool,
    config:CmdConfig
) -> CommandLine
{
    let mut args:Vec<String> = vec![path.clone()];

    if let Some(n) = name
    {
        args.push("-name".to_string());
        args.push(n.clone());
    }

    if let Some(t) = tests
    {
        for (k,v) in t.iter()
        {
            args.push(format!("-{k}"));
            args.push(v.clone());
        }
    }

    if let Some(e) = exec
    {
        if e.len()>0
        {
            args.push("-exec".to_string());
            
            for arg in e
            {
                args.push(arg);
            }

            args.push(
                {
                    if single_exec { "+" } else { ";" }
                }.to_string()
            )
        }
    }

    CommandLine::new(
        "find",
        Some(args),
        None,
        None,
        config
    )
}

pub fn Smartctl<S:AsRef<str> + ToString>(dev:S,action:SmartctlActions,config:CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = vec![action.to_string()];

    if let SmartctlActions::Test(t) = action
    {
        args.push(t.to_string());
    }

    args.push(dev.to_string());

    CommandLine::new(
        "smartctl",
        Some(args),
        None,
        None,
        config
    )
}

pub fn LMSensors(config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "sensors",
        Some(vec!["-j".to_string()]),
        None,
        None,
        config
    )
}

pub fn WipeFS (device:&str,all:bool,config:CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = Vec::new();

    if all { args.push("-a".to_string()); }

    args.push(device.to_string());

    CommandLine::new(
        "wipefs",
        Some(args),
        None,
        None,
        config
    )
}

pub fn UdevAdmInfo (name:&str,query:Option<&str>,config:CmdConfig) -> CommandLine
{
    let mut args:Vec<String> = vec!["info".to_string(),"--json=short".to_string()];

    if let Some(q) = query
    {
        args.push(format!("--query={}",q))
    }

    args.push(format!("--name={}",name));

    CommandLine::new(
        "udevadm",
        Some(args),
        None,
        None,
        config
    )
}

pub fn ExportFs(config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "exportfs",
        Some(vec!["-ra".to_string()]),
        None,
        None,
        config
    )
}

pub fn Sensors(config:CmdConfig) -> CommandLine
{
    CommandLine::new(
        "sensors",
        Some(vec!["-j".to_string()]),
        None,
        None,
        config
    )
}