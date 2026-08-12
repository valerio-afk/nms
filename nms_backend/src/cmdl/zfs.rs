use super::*;
use std::collections::HashMap;

pub struct ZPoolAttachArgs
{
    pool:String,
    vdev: String,
    device: String
}

pub struct ZPoolAddArgs
{
    pool:String,
    device: String,
}

pub struct ZPoolReplaceArgs
{
    pool:String,
    device: String,
    new_device:Option<String>
}

pub struct ZPoolDestroyArgs
{
    pub pool:String,
    pub force:bool
}

pub type ZPoolImportArgs = ZPoolDestroyArgs;

pub struct ZPoolCreateArgs
{
    devices:Vec<String>,
    pool: String,
    redudancy:bool,
    encryption:Option<String>,
    compression:bool,
    posix_acl:bool
}

pub enum ZPoolActions
{
    LabelClear(String),
    Attach(ZPoolAttachArgs),
    Replace(ZPoolReplaceArgs),
    Add(ZPoolAddArgs),
    Destroy(ZPoolDestroyArgs),
    Import(Option<ZPoolImportArgs>),
    Export(String),
    Create(ZPoolCreateArgs),
    Scrub(String),
    Clear(String),
    List(String),
    Status(String),
    Get(String),
}

pub enum ZFSQuota
{
    Bytes(u64),
    Formatted(String)
}

impl std::fmt::Display for ZFSQuota
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

pub struct ZFSArgs<S>
where S:AsRef<str> + ToString + Display
{
    pub pool:S,
    pub dataset: Option<S>
}

impl<S> Display for ZFSArgs<S>
where S:AsRef<str> + ToString + Display
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        let mut s = self.pool.to_string();

        if let Some(dataset) = &self.dataset
        {
            s.push('/');
            s.push_str(dataset.as_ref());
        }

        write!(f,"{}",s)
    }
}

pub struct ZFSQuotaArgs
{
    pub username:String,
    pub quota:ZFSQuota
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

pub struct ZFSListArgs<S>
where S:AsRef<str> + ToString
{
    properties: Option<Vec<S>>,
    list_type: Option<ZFSListType>,
    dataset:Option<String>

}

impl<S> ZFSListArgs<S>
where S:AsRef<str> + ToString
{
    pub fn new(
        properties: Option<Vec<S>>,
        list_type: Option<ZFSListType>,
        dataset: Option<String>
    ) -> Self
    {
        ZFSListArgs { properties, list_type, dataset }
    }
}

impl ZFSListArgs<String>
{
    pub fn new_with_no_args(
        list_type:Option<ZFSListType>,
        dataset:Option<String>
    ) -> ZFSListArgs<String> //I have to put something
    {
        ZFSListArgs { properties: None, list_type, dataset }
    }
}

pub struct ZFSLoadKeyArgs<S>
{
    pub pool:S,
    pub key_path:S,
}

pub struct ZFSSnapshotArgs<S>
where S:AsRef<str> + ToString + Display
{
    pool:S,
    dataset:S,
    snapshot:S
}

impl<S> Display for ZFSSnapshotArgs<S>
where S:AsRef<str> + ToString + Display
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result 
    {
        write!(f,"{}@{}",
            ZFSArgs{pool:self.pool.to_string(),dataset:Some(self.dataset.to_string())}.to_string(),
            self.snapshot
        )    
    }
}


pub enum ZFSActions<S>
where S:AsRef<str> + ToString + Display
{
    GetQuota(ZFSArgs<S>),
    SetQuota(ZFSArgs<S>,ZFSQuotaArgs),
    Get(Option<String>), //pool name
    List(ZFSListArgs<S>),
    LoadKey(ZFSLoadKeyArgs<S>),
    UnloadKey(S), //pool name
    Create(ZFSArgs<S>,Option<HashMap<String, String>>), //options
    Destroy(ZFSArgs<S>,Option<S>), //snapshot nane
    Snapshot(ZFSSnapshotArgs<S>),
    Rollback(ZFSSnapshotArgs<S>),
    Mount(ZFSArgs<S>),
    Unmount(ZFSArgs<S>)
}

pub fn ZPool(
    action:ZPoolActions,
    revertible:bool,
    config:CmdConfig
) -> CommandLine
{
    let mut args : Vec<String> = Vec::new();
    let mut rev_cmd:Option<CommandLine> = None;
    let json_params = &["-p".to_string(),"-j".to_string()];

    match action
    {
        ZPoolActions::Scrub(pool_name) => {
            args.push("scrub".to_string());
            args.push(pool_name);
        },
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
                    Some(ZPoolImportArgs{
                        pool: pool,
                        force:true
                    })
                ),false,config.clone()));
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
                args.push("import".to_string());
                if let Some(p) = &params
                {
                    if p.force
                    {
                        args.push("-f".to_string());
                    }
                    args.push(p.pool.to_string());

                    if revertible 
                    {
                        rev_cmd = Some(ZPool(ZPoolActions::Export(params.unwrap().pool),false,config.clone()));
                    }
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
                ),false,config.clone()));
            }

        }

        ZPoolActions::List(pool) => {
            args.push("list".to_string());
            args.extend_from_slice(json_params);
            args.push(pool.to_string());
        },
        ZPoolActions::Status(pool) => {
            args.push("status".to_string());
            args.extend_from_slice(json_params);
            args.push(pool.to_string());
        },
        ZPoolActions::Get(pool) => {
            args.push("get".to_string());
            args.extend_from_slice(json_params);
            args.push(pool.to_string());
        },
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


pub fn ZFS<S>(action:ZFSActions<S>,revertible:bool,config:CmdConfig) -> CommandLine
where S:AsRef<str> + Display
{
    let mut args:Vec<String> = Vec::new();
    let mut rev_cmd:Option<CommandLine> = None;

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
                ];
                
                if let Some(pool) = pool
                {
                    args.push(pool.to_string());
                }
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
                    rev_cmd = Some(ZFS(ZFSActions::UnloadKey::<S>(p.pool),false,config.clone()));
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
                    rev_cmd = Some(ZFS(ZFSActions::Destroy::<S>(p, None),false,config.clone()));
                }
            }
        ZFSActions::Destroy(p,snapshot) => 
            {
                let fs:String;

                if let Some(tag) = snapshot && let Some(dataset) = p.dataset
                {
                    fs = ZFSSnapshotArgs{
                        pool:p.pool,
                        dataset,
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
                        ZFSActions::Destroy::<S>(ZFSArgs { pool: p.pool, dataset: Some(p.dataset) }, Some(p.snapshot)),
                        false,
                        config.clone()
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
                    rev_cmd = Some(ZFS(ZFSActions::Unmount::<S>(p),false,config.clone()));
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
                    rev_cmd = Some(ZFS(ZFSActions::Mount::<S>(p),false,config.clone()));
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