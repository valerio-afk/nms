use super::Quota;
use crate::cmdl::coreutils::{Cat, Stat, MV, Chown, Chmod, OSUser, FileSystemPermissions, GetID, ID};
use crate::cmdl::passwd::{UserAdd, UserMod, UserModAction};
use crate::cmdl::zfs::{ZFS, ZFSActions, ZFSArgs};
use crate::cmdl::{CmdConfig, Executable, Transaction};
use chrono::{NaiveDateTime,DateTime};
use core::result::Result;
use regex::Regex;
use std::collections::HashMap;
use std::env::temp_dir;
use std::io::Write;
use std::fmt::{Display, Formatter};
use std::fs::{read_to_string, File};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use serde_json::Value;
use case_insensitive_hashmap::CaseInsensitiveHashMap;
use serde::{Serialize, Serializer};
use serde::ser::SerializeStruct;
use crate::backend::config::CfgDynDNS;
use crate::backend::msg::{LogWarnings, LoggerMessages};
use crate::backend::remote_access::ServiceError;
use crate::cmdl::error_filters::stderr_contains;

static DISTRO_FAMILY:OnceLock<DistroFamily> = OnceLock::new();
static SUDO_GROUP:OnceLock<&'static str> = OnceLock::new();
static MBOX_BASEPATH:OnceLock<String> = OnceLock::new();
//
pub static NOTIFICATION_READ_HEADER:&'static str = "X-Notification-Read";

#[derive(PartialEq)]
pub enum DistroFamily
{
    Deb,
    Rh,
    Unk
}

impl Display for DistroFamily
{
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result
    {
        match self
        {
            DistroFamily::Deb => write!(f,"Debian"),
            DistroFamily::Rh => write!(f,"RedHat"),
            DistroFamily::Unk => write!(f,"Unknown")
        }    
    }
}


#[derive(Clone)]
pub struct InboxMail
{
    from:String,
    date:NaiveDateTime,
    headers: CaseInsensitiveHashMap<String>,
    id: String,
    body: String,
}

impl InboxMail
{
    pub fn get_id(&self) -> &str
    {
        &self.id
    }

    pub fn as_read(&mut self)
    {
        self.headers.insert(NOTIFICATION_READ_HEADER.to_string(),"1".to_string());
    }
}

impl Display for InboxMail
{
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result
    {
        writeln!(f,"{}",self.from)?;

        for (k,v) in self.headers.iter()
        {
            writeln!(f,"{}: {}",k,v)?;
        }

        writeln!(f,"\n{}\n",self.body)
    }
}

impl Serialize for InboxMail
{
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut state = serializer.serialize_struct("MBoxMail", 5)?;

        let subject = if let Some(s) = self.headers.get("Subject") {s} else {&String::from("")};

        state.serialize_field("timestamp", &self.date)?;
        state.serialize_field("id", &self.id)?;
        state.serialize_field("subject", subject)?;
        state.serialize_field("read", &(self.headers.get(NOTIFICATION_READ_HEADER).unwrap_or(&String::from("0")) == "1") )?;
        state.serialize_field("body", &self.body)?;

        state.end()
    }
}

impl TryFrom<&HashMap<&'static str,Value>> for InboxMail
{
    type Error = anyhow::Error;
    fn try_from(value:&HashMap<&'static str,Value>) -> Result<Self,Self::Error>
    {
        let from = value
            .get("from")
            .ok_or(anyhow::Error::msg("`From` value missing"))?
            .as_str()
            .ok_or(anyhow::Error::msg("`From` value is not a string"))?
            .to_string();

        let date = value
            .get("date")
            .ok_or(anyhow::Error::msg("`date` value missing"))?
            .as_str()
            .ok_or(anyhow::Error::msg("`date` value is not a string"))?;

        let date = NaiveDateTime::parse_from_str(date, "%a %b %-d %H:%M:%S %Y")?;

        let headers:CaseInsensitiveHashMap<String> = value
            .get("headers")
            .ok_or(anyhow::Error::msg("`headers` value missing"))?
            .as_object()
            .ok_or(anyhow::Error::msg("`headers` is not an object"))?
            .iter()
            .filter_map(|(k,v)|
                if let Some(value) = v.as_str()
                {
                    Some((k.clone(), value.to_string()))
                }
                else { None }
            )
            .into_iter()
            .collect();

        let id  = value
            .get("id")
            .ok_or(anyhow::Error::msg("`id` value missing"))?
            .as_str()
            .ok_or(anyhow::Error::msg("`id` value is not a string"))?
            .to_string();

        let body  = value
            .get("body")
            .ok_or(anyhow::Error::msg("`body` value missing"))?
            .as_str()
            .ok_or(anyhow::Error::msg("`body` value is not a string"))?
            .to_string();

        Ok(InboxMail {
            from,
            date,
            headers,
            id,
            body
        })


    }
}

pub fn init_mbox_basepath(path:Option<String>) -> &'static str
{
    MBOX_BASEPATH.get_or_init( || path.unwrap_or_else(|| String::from("/var/mail"))).as_str()
}

pub fn get_mbox_basepath() -> &'static str { init_mbox_basepath(None) }

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


pub fn str_to_i64 (s:Option<&str>) -> Option<i64>
{
    if let Some(t) = s
    {
        match t.parse::<i64>()
        {
            Ok(int) =>
                {
                    let offset = chrono::Local::now().offset().local_minus_utc() as i64;
                    return Some(int + offset);
                },
            _ => ()
        }
    }

    None
}
pub fn ts_to_str(ts:Option<i64>) -> String
{
    if let Some(timestamp) = ts && let Some(dt) = DateTime::from_timestamp_secs(timestamp)
    {
        return dt.format("%c").to_string();
    }

    return "-".to_string()
}

pub async fn get_quota_for_all(pool:&str, dataset:&str) -> Result<HashMap<String,Quota>,String>
{
    let output = ZFS(
        ZFSActions::GetQuota::<&str>(ZFSArgs{
            pool: pool,
            dataset: Some(dataset)
        }),
        false,
        CmdConfig::default()
    )
    .run()
    .await.map_err(|e| e.to_string())?
    .ok_or_else(|| "No quota found".to_string())?
    .is_success()
    .map_err(|e| e.to_string())?;


    let mut map:HashMap<String,Quota> = HashMap::new();

    for line in output.stdout.lines()
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

        return Ok(map);
    }

    return Err("Unable to execute zfs".to_string());
}

pub async fn get_notifications_count(username:&str) -> u32
{
    let mut n_notifications:u32 = 0;


    let mail_file: PathBuf = Path::new(get_mbox_basepath()).join(username);
    let stat_result = Stat(mail_file.to_str().unwrap(),None,CmdConfig::default()).run().await;


    if let Ok(r) = stat_result && let Some(stat) = r && stat.exit_code == 0
    {
        let cat_result = Cat(Some(mail_file.to_str().unwrap()),CmdConfig::default()).run().await;
        if let Ok(r) = cat_result && let Some(cat) = r && cat.exit_code == 0
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
                    else if l.find(NOTIFICATION_READ_HEADER).is_some()
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


    return n_notifications;
}



pub async fn parse_mbox(username:&str) -> Vec<InboxMail>
{
    let mut mails:Vec<InboxMail> = Vec::new();

    let mail_file: PathBuf = Path::new(get_mbox_basepath()).join(username);
    let stat_result = Stat(mail_file.to_str().unwrap(), None, CmdConfig::default()).run().await;


    if let Ok(r) = stat_result && let Some(stat) = r && stat.exit_code == 0
    {
        let cat_result = Cat(Some(mail_file.to_str().unwrap()),CmdConfig::default()).run().await;
        if let Ok(r) = cat_result && let Some(cat) = r && cat.exit_code == 0
        {
            let mut current_mail:HashMap<&'static str,Value> = HashMap::new();
            let mut last_header:Option<String> = None;
            let mut body_started = false;
            let mut body = String::new();

            let pattern_begin = Regex::new(r"^From [a-zA-Z0-9_-]+(@[a-zA-Z0-9_\-.]+)?\s+(.*)$").unwrap();
            let pattern_header = Regex::new(r"^([a-zA-Z0-9_-]+):\s*(.*)$").unwrap();
            let pattern_header_cnt = Regex::new(r"^(\s+)(.*)$").unwrap();
            let pattern_msg_id = Regex::new(r"^\s*<([0-9a-zA-Z.-]+)(@(.+))?>\s*$").unwrap();

            for l in cat.stdout.lines()
            {
                if let Some(m) = pattern_begin.captures(l)
                {
                    body_started = false;
                    if current_mail.len() > 0
                    {
                        current_mail.insert("body", Value::String(body.trim().to_string()));
                        match InboxMail::try_from(&current_mail)
                        {
                            Ok(mail) => mails.push(mail),
                            Err(e) => LoggerMessages::Warning(LogWarnings::MailParsingError(e.to_string().as_str())).log()
                        }
                    }

                    current_mail.clear();
                    current_mail.insert("from", Value::String(l.trim().to_string()));
                    current_mail.insert("date", Value::String(m[2].to_string()));

                    continue;
                }

                if !body_started
                {
                    if let Some(m) = pattern_header.captures(l)
                    {
                        let hdr = m[1].to_string();
                        let hdr_lc = hdr.to_lowercase();
                        let value = m[2].to_string();

                        last_header = Some(hdr.to_string());

                        if hdr_lc == "message-id"
                        {
                            if let Some(id_m) = pattern_msg_id.captures(&value)
                            {
                                current_mail.insert("id", Value::String(id_m[1].to_string()));
                            }
                        }
                        // else if hdr_lc == "date"
                        // {
                        //     current_mail.insert("date", Value::String(value.to_string()));
                        // }

                        let mut headers = if let Some(h) = current_mail.remove("headers")
                        { serde_json::from_value(h).unwrap() }
                        else { HashMap::new() };
                        headers.insert(hdr,value);
                        current_mail.insert("headers", serde_json::to_value(headers).unwrap());
                    }
                    if let Some(m) = pattern_header_cnt.captures(l) && let Some(last_hdr) = last_header.as_ref()
                    {
                        let h = current_mail.remove("headers").unwrap(); //if we are here, it must be there - unwrap should be safe
                        let mut headers:HashMap<String,String> = serde_json::from_value(h).unwrap();
                        let (k,mut v) = headers.remove_entry(last_hdr).unwrap();
                        v.push_str(&m[0]);
                        headers.insert(k,v);
                        current_mail.insert("headers", serde_json::to_value(headers).unwrap());
                    }
                    if l.trim().len() == 0
                    {
                        body = String::new();
                        body_started = true;
                    }
                }
                else
                {
                    body+=&format!("\n{}",l);
                }
            }

            if current_mail.len() > 0
            {
                current_mail.insert("body", Value::String(String::from(body.trim())));

                match InboxMail::try_from(&current_mail)
                {
                    Ok(mail) => mails.push(mail),
                    Err(e) => LoggerMessages::Warning(LogWarnings::MailParsingError(e.to_string().as_str())).log()
                }
            }
        }
    }

    mails
}

pub async fn flush_mailbox(username:&str, mailbox:&[&InboxMail]) -> Result<(), anyhow::Error>
{
    let file_content = mailbox.iter().map(|m|m.to_string()).collect::<Vec<String>>().join("");
    let mail_filename = format!("{}/{}",get_mbox_basepath(), username);
    let tmp_filename = format!("{username}.mail");

    let mut tmp_fullpath = temp_dir();
    tmp_fullpath.push(tmp_filename);

    let mut handle = File::create(&tmp_fullpath)?;
    handle.write_all(file_content.as_bytes())?;

    MV(tmp_fullpath.to_str().unwrap(),mail_filename.clone(),CmdConfig::default())
        .run()
        .await?;

    Ok(())
}


pub async fn get_user_uid(username:&str) -> Result<u32,anyhow::Error>
{
    let uid = GetID(username, ID::User, CmdConfig::default())
    .run()
    .await?
    .ok_or_else(|| anyhow::Error::msg(format!("Unable to get user uid for {username}")))?
    .is_success()?
    .stdout
    .trim()
    .parse::<u32>()?;

    Ok(uid)
}

pub async fn get_user_gid(username:&str) -> Result<u32,anyhow::Error>
{
    let gid = GetID(username, ID::Group, CmdConfig::default())
        .run()
        .await?
        .ok_or_else(|| anyhow::Error::msg(format!("Unable to get user gid for {username}")))?
        .is_success()?
        .stdout
        .trim()
        .parse::<u32>()?;

    Ok(gid)
}

pub async fn create_unix_user(username:&str,
                              homedir_basepath: Option<PathBuf>,
                              sudo: bool,
                              mut default_groups:Vec<String>) -> Result<u32, anyhow::Error>
{
    if sudo && let Some(sudo_grp) = SUDO_GROUP.get()
    {
        default_groups.push(sudo_grp.to_string());
    }

    let home_dir:Option<String> = homedir_basepath.clone().map
    (
        |mut p|
            {
                p.push(username);
                p.to_str().unwrap().to_string()
            }
    );

    UserAdd(
        username,
        Some(default_groups.as_slice()),
        home_dir.clone(),
        false,
        CmdConfig::default())
        .run()
        .await?
        .ok_or_else(|| anyhow::Error::msg(format!("Unable to create user {username}")))?
        .is_success()?;

    restore_user_home_dir(homedir_basepath,username).await?;
    get_user_uid(username).await
}

pub async fn try_create_unix_user(username:&str,
                              homedir_basepath: Option<PathBuf>,
                              sudo: bool,
                              default_groups:Vec<String>) -> Result<u32, anyhow::Error>
{
    match create_unix_user(username,homedir_basepath.clone(),sudo,default_groups).await
    {
        Err(_) => { //it can be the user already exists and we just need to change perms and return its uid
            restore_user_home_dir(homedir_basepath,username).await?;
            get_user_uid(username).await
        }
        uid @ Ok(_) => uid
    }
}

pub async fn restore_user_home_dir(homedir_basepath:Option<PathBuf>,username:&str) -> Result<(), anyhow::Error>
{
    let home_dir: Option<String> = homedir_basepath.map
    (
        |mut p|
            {
                p.push(username);
                p.to_str().unwrap().to_string()
            }
    );

    if let Some(home) = home_dir
    {
        let perm = FileSystemPermissions::from_mode(0o700);
        let os_user = OSUser::Name(username.to_string());

        let cmds = vec![
            UserMod(UserModAction::ChangeHomedir(username, &home), false, CmdConfig::default()),
            Chown(&os_user, &os_user, &OSUser::Empty, &OSUser::Empty, home.as_str(), true, CmdConfig::default()),
            Chmod(&perm, None, home, true, CmdConfig::default()),
        ];

        Transaction::new(cmds)
            .accept_error_if(stderr_contains("mail spool"))
            .execute()
            .await?;
    }

    Ok(())
}

