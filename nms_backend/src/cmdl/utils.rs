use std::collections::HashMap;

use super::*;

//["lsblk", "-J", "-b", "-o", "NAME,MODEL,SERIAL,TYPE,TRAN,SIZE,PATH"]

pub enum LsblkProperties
{
    ALIGNMENT,
    IDLINK,
    ID,
    DISCALN,
    DAX,
    DISCGRAN,
    DISKSEQ,
    DISCMAX,
    DISCZERO,
    FSAVAIL,
    FSROOTS,
    FSSIZE,
    FSTYPE,
    FSUSED,
    FSUSE_P,
    FSVER,
    GROUP,
    HCTL,
    HOTPLUG,
    KNAME,
    LABEL,
    LOGSEC,
    MAJ_MIN,
    MINIO,
    MODE,
    MODEL,
    MQ,
    NAME,
    OPTIO,
    OWNER,
    PARTFLAGS,
    PARTLABEL,
    PARTN,
    PARTTYPE,
    PARTTYPENAME,
    PARTUUID,
    PATH,
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
    ZONESZ,
    ZONEWGRAN,
    ZONEAPP,
    ZONENR,
    ZONEOMAX,
    ZONEAMAX,
}

impl std::fmt::Display for LsblkProperties 
{
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result 
    {
        match self 
        {
            LsblkProperties::ALIGNMENT => write!(f,"ALIGNMENT"),
            LsblkProperties::IDLINK => write!(f,"ID-LINK"),
            LsblkProperties::ID => write!(f,"ID"),
            LsblkProperties::DISCALN => write!(f,"DISC-ALN"),
            LsblkProperties::DAX => write!(f,"DAX"),
            LsblkProperties::DISCGRAN => write!(f,"DISC-GRAN"),
            LsblkProperties::DISKSEQ => write!(f,"DISK-SEQ"),
            LsblkProperties::DISCMAX => write!(f,"DISC-MAX"),
            LsblkProperties::DISCZERO => write!(f,"DISC-ZERO"),
            LsblkProperties::FSAVAIL => write!(f,"FSAVAIL"),
            LsblkProperties::FSROOTS => write!(f,"FSROOTS"),
            LsblkProperties::FSSIZE => write!(f,"FSSIZE"),
            LsblkProperties::FSTYPE => write!(f,"FSTYPE"),
            LsblkProperties::FSUSED => write!(f,"FSUSED"),
            LsblkProperties::FSUSE_P => write!(f,"FSUSE%"),
            LsblkProperties::FSVER => write!(f,"FSVER"),
            LsblkProperties::GROUP => write!(f,"GROUP"),
            LsblkProperties::HCTL => write!(f,"HCTL"),
            LsblkProperties::HOTPLUG => write!(f,"HOTPLUG"),
            LsblkProperties::KNAME => write!(f,"KNAME"),
            LsblkProperties::LABEL => write!(f,"LABEL"),
            LsblkProperties::LOGSEC => write!(f,"LOG-SEC"),
            LsblkProperties::MAJ_MIN => write!(f,"MAJ:MIN"),
            LsblkProperties::MINIO => write!(f,"MIN-IO"),
            LsblkProperties::MODE => write!(f,"MODE"),
            LsblkProperties::MODEL => write!(f,"MODEL"),
            LsblkProperties::MQ => write!(f,"MQ"),
            LsblkProperties::NAME => write!(f,"NAME"),
            LsblkProperties::OPTIO => write!(f,"OPT-IO"),
            LsblkProperties::OWNER => write!(f,"OWNER"),
            LsblkProperties::PARTFLAGS => write!(f,"PARTFLAGS"),
            LsblkProperties::PARTLABEL => write!(f,"PARTLABEL"),
            LsblkProperties::PARTN => write!(f,"PARTN"),
            LsblkProperties::PARTTYPE => write!(f,"PARTTYPE"),
            LsblkProperties::PARTTYPENAME => write!(f,"PARTTYPENAME"),
            LsblkProperties::PARTUUID => write!(f,"PARTUUID"),
            LsblkProperties::PATH => write!(f,"PATH"),
            LsblkProperties::PHYSEC => write!(f,"PHY-SEC"),
            LsblkProperties::PKNAME => write!(f,"PKNAME"),
            LsblkProperties::PTTYPE => write!(f,"PTTYPE"),
            LsblkProperties::PTUUID => write!(f,"PTUUID"),
            LsblkProperties::RA => write!(f,"RA"),
            LsblkProperties::RAND => write!(f,"RAND"),
            LsblkProperties::REV => write!(f,"REV"),
            LsblkProperties::RM => write!(f,"RM"),
            LsblkProperties::RO => write!(f,"RO"),
            LsblkProperties::ROTA => write!(f,"ROTA"),
            LsblkProperties::RQSIZE => write!(f,"RQ-SIZE"),
            LsblkProperties::SCHED => write!(f,"SCHED"),
            LsblkProperties::SERIAL => write!(f,"SERIAL"),
            LsblkProperties::SIZE => write!(f,"SIZE"),
            LsblkProperties::START => write!(f,"START"),
            LsblkProperties::STATE => write!(f,"STATE"),
            LsblkProperties::SUBSYSTEMS => write!(f,"SUBSYSTEMS"),
            LsblkProperties::MOUNTPOINT => write!(f,"MOUNTPOINT"),
            LsblkProperties::MOUNTPOINTS => write!(f,"MOUNTPOINTS"),
            LsblkProperties::TRAN => write!(f,"TRAN"),
            LsblkProperties::TYPE => write!(f,"TYPE"),
            LsblkProperties::UUID => write!(f,"UUID"),
            LsblkProperties::VENDOR => write!(f,"VENDOR"),
            LsblkProperties::WSAME => write!(f,"WSAME"),
            LsblkProperties::WWN => write!(f,"WWN"),
            LsblkProperties::ZONED => write!(f,"ZONED"),
            LsblkProperties::ZONESZ => write!(f,"ZONE-SZ"),
            LsblkProperties::ZONEWGRAN => write!(f,"ZONE-WGRAN"),
            LsblkProperties::ZONEAPP => write!(f,"ZONE-APP"),
            LsblkProperties::ZONENR => write!(f,"ZONE-NR"),
            LsblkProperties::ZONEOMAX => write!(f,"ZONE-OMAX"),
            LsblkProperties::ZONEAMAX => write!(f,"ZONE-AMAX"),
        }
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

pub fn LSBLK<'a,'b>(
    properties:Option<&[LsblkProperties]>,
    config:Option<&'b CmdConfig<'a>>
) -> CommandLine<'a,'b>
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

    CommandLine::new(
        "lsblk",
        Some(args),
        None,
        None,
        config
    )
}

pub fn LSCPU<'a,'b>(config:Option<&'b CmdConfig<'a>>) -> CommandLine<'a,'b>
{
    CommandLine::new(
        "lscpu",
        None,
        None,
        None,
        config
    )
}

pub fn Find<'a,'b>(
    path:&String,
    name:Option<&String>,
    tests:Option<&HashMap<String,String>>,
    exec:Option<&[&String]>,
    single_exec:bool,
    config:Option<&'b CmdConfig<'a>>
) -> CommandLine<'a,'b>
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
            args.push("-name".to_string());
            
            for &arg in e
            {
                args.push(arg.clone());
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

pub fn Smartctl<'a,'b>(dev:&String,action:SmartctlActions,config:Option<&'b CmdConfig<'a>>) -> CommandLine<'a,'b>
{
    let mut args:Vec<String> = vec![action.to_string()];

    if let SmartctlActions::Test(t) = action
    {
        args.push(t.to_string());
    }

    args.push(dev.clone());

    CommandLine::new(
        "smartctl",
        Some(args),
        None,
        None,
        config
    )
}

pub fn LMSensors<'a,'b>(config:Option<&'b CmdConfig<'a>>) -> CommandLine<'a,'b>
{
    CommandLine::new(
        "sensors",
        Some(vec!["-j".to_string()]),
        None,
        None,
        config
    )
}