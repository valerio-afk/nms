use std::path::{Path, PathBuf};
use std::fs::read_to_string;
use std::collections::HashMap;
use std::sync::OnceLock;
use regex::Regex;
use core::result::Result;
use super::Quota;
use crate::cmdl::{CmdConfig, Executable};
use crate::cmdl::coreutils::{Stat,Cat};
use crate::cmdl::zfs::{ZFS, ZFSActions, ZFSArgs};

static DISTRO_FAMILY:OnceLock<DistroFamily> = OnceLock::new();
static SUDO_GROUP:OnceLock<&'static str> = OnceLock::new();
const MBOX_BASEPATH:&str = "/var/mail";

#[derive(PartialEq)]
pub enum DistroFamily
{
    Deb,
    Rh,
    Unk
}

impl std::fmt::Display for DistroFamily
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        match self
        {
            DistroFamily::Deb => write!(f,"Debian"),
            DistroFamily::Rh => write!(f,"RedHat"),
            DistroFamily::Unk => write!(f,"Unknown")
        }    
    }
}

pub fn detect_distro_family() -> &'static DistroFamily
{
    DISTRO_FAMILY.get_or_init( || {
        let file = read_to_string("/etc/os-release");

        if let Ok(handle) = file
        {
            let mut os_release:HashMap<String,String> = HashMap::new();

            for line in handle.lines()
            {
                if (line.len()==0) || (line.find("=")==None) { continue; }

                let tokens:Vec<&str> = line.splitn(2,"=").collect();

                os_release.insert(
                    tokens[0].trim().to_string(),
                    tokens[1].trim().to_string()
                );
            }

            let id_like = os_release.get(&"ID_LIKE".to_string());
            let id = os_release.get(&"ID".to_string());

            if let Some(id) = id_like
            {
                let id = id.to_lowercase();

                if let Some(_) = id.find("debian") { return DistroFamily::Deb; }

                if vec!["rhel","fedora"].iter().any(|x| id.find(x) != None) { return DistroFamily::Rh; }
            }

            if let Some(nm) = id
            {
                let nm = nm.to_lowercase();
                if vec!["debian", "ubuntu", "raspbian"].iter().any(|x| x == &nm) { return DistroFamily::Deb; }
                if vec!["rhel", "fedora", "centos", "rocky", "almalinux"].iter().any(|x| x == &nm) { return DistroFamily::Rh; }
            }


        }
        
        return DistroFamily::Unk;
    })
}

pub fn sudo_group() -> &'static str
{
    SUDO_GROUP.get_or_init(||{
        match detect_distro_family()
        {
            DistroFamily::Deb => "sudo",
            _ => "wheel"
        }
    })
}

pub fn get_quota_for_all(pool:&str, dataset:&str) -> Result<HashMap<String,Quota>,String>
{
    let config = CmdConfig::new(true, true, None, None);
    let output = ZFS(
        ZFSActions::GetQuota(ZFSArgs{
            pool, dataset
        }),
        false,
        Some(&config)
    ).run();

    if let Some(o) = output
    {
        if o.status_code != 0 { return Err(format!("Unable to get quota (status code: {}): {}",o.status_code,o.stderr)); }

        let mut map:HashMap<String,Quota> = HashMap::new();

        for line in o.stdout.lines()
        {
            let tokens:Vec<&str> = line.splitn(3,"\t").collect();

            if tokens.len() == 3
            {
                let uname = tokens[0].trim();
                let used:Option<u64> = match tokens[1].trim().parse::<u64>()
                {
                    Ok(q) => Some(q),
                    Err(_) => None
                };

                let limit:Option<u64> = match tokens[2].trim().parse::<u64>()
                {
                    Ok(q) => Some(q),
                    Err(_) => None
                };

                map.insert(uname.to_string(),Quota {
                    quota:limit,
                    used: used
                });
            }
        }

        return Ok(map);
    }

    return Err("Unable to execute zfs".to_string());
}

pub fn get_notifications_count(username:&str) -> u32
{
    let mut n_notifications:u32 = 0;

    let cfg = CmdConfig::new(true,true,None,None);
    let mail_file: PathBuf = Path::new(MBOX_BASEPATH).join(username);
    let stat_result = Stat(mail_file.to_str().unwrap(),None,Some(&cfg)).run();

    if let Some(stat) = stat_result
    {
        if stat.status_code == 0
        {
            let cat_result = Cat(Some(mail_file.to_str().unwrap()),Some(&cfg)).run();

            if let Some(cat) = cat_result
            {
                if cat.status_code == 0
                {
                    let pattern = Regex::new(r"^From[^:](.*)$");

                    if let Ok(re) = pattern
                    {
                        for l in cat.stdout.lines()
                        {
                            if re.is_match(l)
                            { 
                                n_notifications+=1; 
                            }
                            else if l.find("X-Notification-Read").is_some()
                            {
                                let tokens:Vec<&str> = l.trim().split(":").collect();

                                if tokens.len()==2
                                {
                                    if let Ok(n) = tokens[1].trim().parse::<u32>()
                                    {
                                        if n==1 {n_notifications-=1;}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }


    return n_notifications;
}