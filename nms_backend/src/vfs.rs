use std::str::FromStr;
use std::{path::PathBuf};
use crate::cmdl::{zfs::{ZFS, ZFSActions, ZFSListArgs, ZFSListType, ZPool, ZPoolActions}, CmdConfig, Executable};
use serde::Serialize;
use serde_json::Value;
pub enum FileType 
{
    Regular,
    Directory(Vec<File>),
    Link
}


pub struct File
{
    pub name:String,
    pub filetype:FileType,
    pub size: usize,
}

#[derive(Clone, Serialize)]
pub struct Capacity
{
    pub used: u128,
    pub total: u128,
}

impl Capacity
{
    pub async fn from_zfs(pool_name:&str) -> Result<Self,Option<String>>
    {
        let cmd = ZPool(ZPoolActions::List(pool_name.to_string()), false, CmdConfig::Empty);
        
        if let Some(output) = cmd.run().await.map_err(|e| Some(e.to_string()))?
        {
            if output.exit_code != 0 { return Err(Some(output.stderr)); }
            let zpool_list:Value = serde_json::from_str(&output.stdout).map_err(|x| Some(x.to_string()))?;

            if let Value::Object(prop) = &zpool_list["pools"][pool_name]["properties"]
            {
                let allocated = &prop["allocated"]["value"];
                let size = &prop["size"]["value"];

                if allocated.is_string() && size.is_string()
                {
                    return Ok(Capacity{
                        used: allocated.to_string().parse::<u128>().map_err(|x| Some(x.to_string()))?,
                        total: size.to_string().parse::<u128>().map_err(|x| Some(x.to_string()))?,
                    });
                }
            }
        }

        Err(None)
    }
}

pub struct VFS
{
    pub basepath: PathBuf,
    pub root: File,
    pub capacity: Capacity
}

impl VFS
{
    pub async fn from_zfs(pool:&str,dataset:&str) -> Result<Self,Option<String>>
    {
        //let basepath = PathBuf::from_str(basepath).unwrap();
        //let capacity = Capacity::from_zfs(&basepath);

        let key:String = format!("{}/{}",pool, dataset);

        let cmd = ZFS(
            ZFSActions::List(
                ZFSListArgs::new(
                    Some(vec!["mountpoint"]),
                    Some(ZFSListType::Filesystem),
                    Some(key.clone())
                )
            ), 
            false, 
            CmdConfig::Empty);

        if let Some(output) = cmd.run().await.map_err(|e| Some(e.to_string()))?
        {
            if output.exit_code != 0 { return Err(Some(output.stderr)); }

            let zfs_list:Value = serde_json::from_str(&output.stdout).map_err(|x| Some(x.to_string()))?;

            if let Value::String(mp) = &zfs_list["datasets"][key]["properties"]["mountpoint"]["value"]
            {
                let basepath = PathBuf::from_str(mp).map_err(|x| Some(x.to_string()))?;

                return Ok(VFS { 
                    basepath, 
                    root: File {
                        name: "".to_string(),
                        filetype: FileType::Directory(Vec::new()),
                        size: 0
                    },
                    capacity: Capacity::from_zfs(pool).await?
                });
            }
        }
        Err(None)
    }

    pub fn basepath(&self) -> PathBuf
    {
        return self.basepath.clone();
    }

}