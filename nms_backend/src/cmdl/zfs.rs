use super::*;
use std::collections::HashMap;

pub struct ZPoolAttachArgs<'a>
{
    pool:&'a str,
    vdev: &'a str,
    device: &'a str
}

pub struct ZPoolAddArgs<'a>
{
    pool:&'a str,
    device: &'a str,
}

pub struct ZPoolReplaceArgs<'a>
{
    pool:&'a str,
    device: &'a str,
    new_device:Option<&'a str>
}

pub struct ZPoolDestroyArgs<'a>
{
    pool:&'a str,
    force:bool
}

type ZPoolImportArgs<'a> = ZPoolDestroyArgs<'a>;

pub struct ZPoolCreateArgs<'a>
{
    devices:&'a[&'a str],
    pool: &'a str,
    redudancy:bool,
    encryption:Option<&'a str>,
    compression:bool,
    posix_acl:bool
}

pub enum ZPoolActions<'a>
{
    LabelClear(&'a str),
    Attach(ZPoolAttachArgs<'a>),
    Replace(ZPoolReplaceArgs<'a>),
    Add(ZPoolAddArgs<'a>),
    Destroy(ZPoolDestroyArgs<'a>),
    Import(ZPoolImportArgs<'a>),
    Export(&'a str),
    Create(ZPoolCreateArgs<'a>),
    Scrub,
    Clear(&'a str),
    List(&'a str),
    Status(&'a str),
    Get(&'a str),
}

pub enum ZFSQuota<'a>
{
    Bytes(u64),
    Formatted(&'a str)
}

impl<'a> std::fmt::Display for ZFSQuota<'a>
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        match self
        {
            ZFSQuota::Bytes(num) => write!(f,"{num}"),
            ZFSQuota::Formatted(s) => write!(f,"{s}")
        }    
    }
}

pub struct ZFSArgs<'a>
{
    pub pool:&'a str,
    pub dataset: &'a str
}

impl<'a> std::fmt::Display for ZFSArgs<'a>
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        write!(f,"{}/{}",self.pool,self.dataset)
    }
}

pub struct ZFSQuotaArgs<'a>
{
    username:&'a str,
    quota:ZFSQuota<'a>
}

pub enum ZFSListType
{
    Filesystem,
    Snapshot,
    Volume,
    Bookmark,
    All
}

impl std::fmt::Display for ZFSListType
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        match self
        {
            ZFSListType::Filesystem => write!(f,"filesystem"),
            ZFSListType::Snapshot => write!(f,"snapshot"),
            ZFSListType::Volume => write!(f,"volume"),
            ZFSListType::Bookmark => write!(f,"bookmark"),
            ZFSListType::All => write!(f,"all"),
        }    
    }
}

pub struct ZFSListArgs<'a>
{
    properties: Option<&'a [&'a str]>,
    list_type: Option<ZFSListType>,
    dataset:Option<&'a str>

}

impl<'a> ZFSListArgs<'a>
{
    pub fn new(properties:Option<&'a [&'a str]>,list_type:Option<ZFSListType>,dataset:Option<&'a str>) -> Self
    {
        ZFSListArgs { properties, list_type, dataset }
    }
}

pub struct ZFSLoadKeyArgs<'a>
{
    pool:&'a str,
    key_path:&'a str,
}

// pub struct ZFSCreateArgs<'a>
// {
//     pool:&'a str,
//     dataset:&'a str,
//     options:Option<&'a [&'a str]>
// }

// pub struct ZFSDestroyArgs<'a>
// {
//     pool:&'a str,
//     dataset:&'a str,
//     snapshot:Option<&'a str>
// }

pub struct ZFSSnapshotArgs<'a>
{
    pool:&'a str,
    dataset:&'a str,
    snapshot:&'a str
}

impl<'a> std::fmt::Display for ZFSSnapshotArgs<'a>
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        write!(f,"{}@{}",
            ZFSArgs{pool:self.pool,dataset:self.dataset}.to_string(),
            self.snapshot
        )    
    }
}


pub enum ZFSActions<'a>
{
    GetQuota(ZFSArgs<'a>),
    SetQuota(ZFSArgs<'a>,ZFSQuotaArgs<'a>),
    Get(&'a str), //pool name
    List(ZFSListArgs<'a>),
    LoadKey(ZFSLoadKeyArgs<'a>),
    UnloadKey(&'a str), //pool name
    Create(ZFSArgs<'a>,Option<HashMap<&'a str, &'a str>>), //options
    Destroy(ZFSArgs<'a>,Option<&'a str>), //snapshot nane
    Snapshot(ZFSSnapshotArgs<'a>),
    Rollback(ZFSSnapshotArgs<'a>),
    Mount(ZFSArgs<'a>),
    Unmount(ZFSArgs<'a>)
}

pub fn ZPool<'a,'b>(
    action:ZPoolActions<'a>,
    revertible:bool,
    config:Option<&'b CmdConfig<'a>>
) -> CommandLine<'a,'b>
{
    let mut args : Vec<String> = Vec::new();
    let mut rev_cmd:Option<CommandLine<'a,'b>> = None;

    match action
    {
        ZPoolActions::Scrub => args.push("scrub".to_string()),
        ZPoolActions::LabelClear(dev) => {
            args.push("labelclear".to_string());
            args.push(dev.to_string());
        },
        ZPoolActions::Export(pool) => {
            args.push("export".to_string());
            args.push(pool.to_string());
            
            if revertible
            {
                rev_cmd = Some(ZPool(ZPoolActions::Import(
                    ZPoolImportArgs{
                        pool: pool,
                        force:true
                    }
                ),false,config));
            }
        },
        ZPoolActions::Clear(pool) => {
            args.push("clear".to_string());
            args.push(pool.to_string());
        },
        ZPoolActions::Attach(params) => {
                args.push("attach".to_string());
                args.push(params.pool.to_string());
                args.push(params.vdev.to_string());
                args.push(params.device.to_string());
        }

        ZPoolActions::Replace(params) => {
                args.push("replace".to_string());
                args.push(params.pool.to_string());
                args.push(params.device.to_string());

                if let Some(n_dev) = params.new_device
                {
                    args.push(n_dev.to_string());
                }
        }

        ZPoolActions::Add(params) => {
                args.push("add".to_string());
                args.push(params.pool.to_string());
                args.push(params.device.to_string());

        }

        ZPoolActions::Destroy(params) => {
                args.push("add".to_string());
                if params.force
                {
                    args.push("-f".to_string());
                }
                args.push(params.pool.to_string());
        }

        ZPoolActions::Import(params) => {
                args.push("add".to_string());
                if params.force
                {
                    args.push("-f".to_string());
                }
                args.push(params.pool.to_string());

                if revertible
                {
                    rev_cmd = Some(ZPool(ZPoolActions::Export(params.pool),false,config));
                }
        }

        ZPoolActions::Create(params) => {
            args.extend_from_slice(&[
                "create".to_string(),
                "-f".to_string(),
                "-o".to_string(),
                "ashift=12".to_string()
            ]);

            if params.compression
            {
                args.extend_from_slice(&[
                    "-O".to_string(),
                    "compression=lz4".to_string(),
                ]);
            }

            if params.posix_acl
            {
                args.extend_from_slice(&[
                    "-O".to_string(),
                    "acltype=posixacl".to_string(),
                ]);
            }

            if let Some(key) = params.encryption
            {
                args.extend_from_slice(&[
                    "-O".to_string(),
                    "encryption=aes-256-gcm".to_string(),
                    "-O".to_string(),
                    "keyformat=raw".to_string(),
                    "-O".to_string(),
                    format!("keylocation=file://{key}")
                ]);
            }

            args.push(params.pool.to_string());

            if params.redudancy
            {
                args.push("raidz1".to_string());
            }

            for dev in params.devices
            {
                args.push(dev.to_string());
            }

            if revertible
            {
                rev_cmd = Some(ZPool(ZPoolActions::Destroy(
                    ZPoolDestroyArgs { pool: params.pool, force: true },
                ),false,config));
            }

        }

        _ =>{
                args.extend_from_slice(&["-p".to_string(),"-J".to_string()]); //json output
                match action
                {
                    ZPoolActions::List(pool) => {
                        args.push("export".to_string());
                        args.push(pool.to_string());
                    },
                    ZPoolActions::Status(pool) => {
                        args.push("export".to_string());
                        args.push(pool.to_string());
                    },
                    ZPoolActions::Get(pool) => {
                        args.push("export".to_string());
                        args.push(pool.to_string());
                    },
                    _ => ()
                }
            }
        

    }

    CommandLine::new(
        "zpool",
        Some(args),{
            if let Some(cmd) = rev_cmd { Some(Box::new(cmd)) } else {None}
        },
        None,
        config
    )
}


// pub enum ZFSActions<'a>
// {
//     GetQuota(ZFSArgs<'a>),
//     SetQuota(ZFSQuotaArgs<'a>),
//     Get(&'a str),
//     List(ZFSListArgs<'a>),
//     LoadKey(ZFSLoadKeyArgs<'a>),
//     UnloadKey(&'a str),
//     Create(ZFSCreateArgs<'a>),
//     Destroy(ZFSDestroyArgs<'a>),
//     Snapshot(ZFSSnapshotArgs<'a>),
//     Rollback(ZFSSnapshotArgs<'a>),
//     Mount(ZFSMountArgs<'a>),
//     Unmount(ZFSMountArgs<'a>)
// }
pub fn ZFS<'a,'b>(action:ZFSActions,revertible:bool,config:Option<&'b CmdConfig<'a>>) -> CommandLine<'a,'b>
{
    let mut args:Vec<String> = Vec::new();
    let mut rev_cmd:Option<CommandLine<'a,'b>> = None;

    match action
    {
        ZFSActions::GetQuota(p) =>
            {
                args = vec![
                    "userspace".to_string(),
                    "-p".to_string(),
                    "-H".to_string(),
                    "-o".to_string(),
                    "name,used,quota".to_string(),
                    p.to_string()
                ];
            }
        ZFSActions::SetQuota(p,quota) =>
            {
                args = vec![
                    "set".to_string(),
                    format!("userquota@{}={}",quota.username,quota.quota.to_string()),
                    p.to_string()
                ];
            }
        ZFSActions::Get(pool) =>
            {
                args = vec![
                    "get".to_string(),
                    "-p".to_string(),
                    "-j".to_string(),
                    "all".to_string(),
                    pool.to_string()
                ];        
            }
        ZFSActions::List(p) =>
            {
                args.extend_from_slice(
                    &[
                        "list".to_string(),
                        "-p".to_string(),
                        "-j".to_string(),
                    ]
                );

                if let Some(props) = p.properties
                {
                    if props.len()>0
                    {
                        args.push("-o".to_string());
                        args.push(props.iter().map(|s| s.to_string()).collect());
                    }
                }

                if let Some(t) = p.list_type
                {
                    args.push("-t".to_string());
                    args.push(t.to_string());
                }

                if let Some(n) = p.dataset
                {
                    args.push(n.to_string());
                }
            }
        ZFSActions::LoadKey(p) =>
            {
                args = vec![
                    "load-key".to_string(),
                    p.pool.to_string(),
                    "-L".to_string(),
                    format!("file://{}",p.key_path)
                ]; 

                if revertible
                {
                    rev_cmd = Some(ZFS(ZFSActions::UnloadKey(p.pool),false,config));
                } 
            }
        ZFSActions::UnloadKey(pool) =>
            {
                args = vec![
                    "unload-key".to_string(),
                    pool.to_string(),
                ];  
            }
        ZFSActions::Create (p,options) =>
            {
                args.push("create".to_string());
                args.push(p.to_string());

                if let Some(opts) = options
                {
                    for (k,v) in opts
                    {
                        args.push("-o".to_string());
                        args.push(format!("{k}={v}"))
                    }
                }

                if revertible
                {
                    rev_cmd = Some(ZFS(ZFSActions::Destroy(p, None),false,config));
                }
            }
        ZFSActions::Destroy(p,snapshot) => 
            {
                let fs:String;

                if let Some(tag) = snapshot
                {
                    fs = ZFSSnapshotArgs{
                        pool:p.pool,
                        dataset:p.dataset,
                        snapshot:tag
                    }.to_string()
                }
                else 
                {
                    fs = p.to_string();    
                }

                args = vec![
                    "destroy".to_string(),
                    fs
                ];
            }
        ZFSActions::Snapshot(p)=>
            {
                args = vec![
                    "snapshot".to_string(),
                    p.to_string()
                ];

                if revertible
                {
                    rev_cmd = Some(ZFS(
                        ZFSActions::Destroy(ZFSArgs { pool: p.pool, dataset: p.dataset }, Some(p.snapshot)),
                        false,
                        config
                    ))
                }
            },
        ZFSActions::Rollback(p)=>
            {
                args = vec![
                    "rollback".to_string(),
                    p.to_string()
                ]  
            },
        ZFSActions::Mount(p)=>
            {
                args = vec![
                    "mount".to_string(),
                    p.to_string()
                ];

                if revertible
                {
                    rev_cmd = Some(ZFS(ZFSActions::Unmount(p),false,config));
                }
            },
        ZFSActions::Unmount(p)=> 
            {
                args = vec![
                    "unmount".to_string(),
                    p.to_string()
                ];

                if revertible
                {
                    rev_cmd = Some(ZFS(ZFSActions::Mount(p),false,config));
                }
            },
    }

    CommandLine::new(
        "zfs",
        Some(args),
        {
            if let Some(cmd) = rev_cmd
            {
                Some(Box::new(cmd))
            }
            else {None}
        },
        None,
        config
    )
}