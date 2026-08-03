use std::str::FromStr;
use std::{path::PathBuf};
use async_recursion::async_recursion;
use futures::StreamExt;
use tokio::fs::read_dir;
use crate::cmdl::{zfs::{ZFS, ZFSActions, ZFSListArgs, ZFSListType, ZPool, ZPoolActions}, CmdConfig, Executable};
use serde::Serialize;
use serde_json::Value;
use tokio_stream::wrappers::ReadDirStream;

#[derive(Debug)]
pub enum FileType
{
    Regular,
    Directory(Vec<VFSEntry>),
    Link
}

#[derive(Debug)]
pub struct VFSEntry
{
    pub name:String,
    pub filetype:FileType,
    pub size: u64,
}

#[derive(Debug, Clone, Serialize)]
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

                if let Some(allocated) = allocated.as_str() && let Some(total) = size.as_str()
                {
                    return Ok(Capacity{
                        used: allocated.parse::<u128>().map_err(|x| Some(x.to_string()))?,
                        total: total.parse::<u128>().map_err(|x| Some(x.to_string()))?,
                    });
                }
            }
        }

        Err(None)
    }
}


#[derive(Debug)]
pub struct VFS
{
    pub basepath: PathBuf,
    pub root: VFSEntry,
    pub capacity: Capacity
}

impl VFS
{
    pub async fn from_zfs(pool:&str,dataset:&str) -> Result<Self,Option<String>>
    {

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
                    root: VFSEntry {
                        name: "/".to_string(),
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

    #[async_recursion]
    async fn build_tree(&mut self, path:PathBuf) -> Option<VFSEntry>
    {
        let dir = read_dir(&path).await;

        if let Err(_) = dir
        {
            return None;
        }

        let dir = dir.unwrap();
        let mut stream = ReadDirStream::new(dir);

        let mut entries:Vec<VFSEntry> = Vec::new();


        while let Some(entry) = stream.next().await
        {
            if let Ok(entry) = entry
            {
                if let Ok(meta) = entry.metadata().await
                {
                    if meta.is_dir()
                    {
                        let subdir = self.build_tree(entry.path()).await;
                        if let Some(subdir) = subdir
                        {
                            entries.push(subdir);
                        }
                    }
                    else if meta.is_file()
                    {
                        entries.push(
                            VFSEntry {
                                name: entry.file_name().into_string().unwrap(),
                                filetype: FileType::Regular,
                                size: meta.len()
                            }
                        )
                    }
                    else if meta.is_symlink()
                    {
                        entries.push(
                            VFSEntry {
                                name: entry.file_name().into_string().unwrap(),
                                filetype: FileType::Link,
                                size: 0
                            }
                        )
                    }
                }
            }
        }

        Some(VFSEntry
        {
            name:{
                if path == self.basepath
                {
                    String::from("/")
                }
                else
                {
                    path.file_name().unwrap().to_str().unwrap().to_string()
                }
            },
            filetype: FileType::Directory(entries),
            size:0
        })
    }

    pub async fn rebuild_tree(&mut self)
    {
        if let Some(tree) =self.build_tree(self.basepath.clone()).await
        {
            self.root = tree;
        }
    }

}