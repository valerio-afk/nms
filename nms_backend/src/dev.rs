use std::unreachable;
use strum::{EnumString, FromRepr};
use serde::{Serialize};
use serde_json::{Value,Map};
use serde_repr::Serialize_repr;
use crate::cmdl::{CmdConfig, Executable};
use crate::cmdl::utils::Find;
use crate::cmdl::utils::{LSBLK, LsblkProperties,UdevAdmInfo};

static ACCEPTED_TRAN_TYPES:[&'static str;3] = ["sata","spi","usb"];
#[derive(Debug, Serialize_repr,FromRepr, PartialEq,EnumString, Clone)]
#[repr(i32)]
#[strum(ascii_case_insensitive)]
pub enum DiskState
{
    NEW = 0,
    ONLINE = -1,

    #[strum(serialize="UNAVAIL")]
    OFFLINE = -2,

    #[strum(serialize="DEGRADED",serialize="FAULTED")]
    CORRUPTED = -3,
    UNKNOWN = -100
}

#[derive(Debug, Serialize, Clone)]
pub struct Device
{
    pub name:String,
    pub paths:Vec<String>,
    pub state:DiskState,
    pub model:Option<String>,
    pub serial_number:Option<String>,
    pub size:u64
}

#[derive(Debug)]
pub enum DeviceError
{
    DeviceNotFound(String),
    LsblkError(String),
}

impl std::fmt::Display for DeviceError {
    fn fmt(&self, f: &mut core::fmt::Formatter) -> Result<(), core::fmt::Error> 
    {
        match self 
        {
            DeviceError::DeviceNotFound(s) => write!(f, "Device {} not found.",s),
            DeviceError::LsblkError(s) => write!(f,"{}", s),
        }
    }
}

impl std::error::Error for DeviceError 
{
    fn description(&self) -> &str 
    {
        match self 
        {
            DeviceError::DeviceNotFound(_) => "Unable to detect device.",
            DeviceError::LsblkError(_) => "Error while executing LSBLK or parsing its output."
        }
    }
}


pub async fn get_dev_paths(device_name:&str) -> Vec<String>
{
    let mut paths:Vec<String> = Vec::new();
    let udev_res = UdevAdmInfo(device_name, Some("all"), CmdConfig::Empty).run().await;

    if let Ok(r) = udev_res && let Some(udev_output) = r && udev_output.exit_code == 0
    {
        let d:Value = serde_json::from_str(&udev_output.stdout).unwrap_or(Value::Null);

        if let Value::String(name) = &d["DEVNAME"]
        {
            paths.push(name.to_string());
        }

        if let Value::String(symlinks) = &d["DEVLINKS"]
        {
            for symlink in symlinks.split(" ")
            {
                paths.push(symlink.trim().to_string());
            }
        }
    }

    return paths;
}


impl Device
{
    pub async fn new(path:&str,state:DiskState) -> Result<Device,DeviceError>
    {
        let lsbkl_result = LSBLK(
            LsblkProperties::default(),
            Some(&path.to_string()),
            CmdConfig::Empty
        ).run().await;

        if let Ok(r) = lsbkl_result && let Some(output) = r
        {
            if output.exit_code == 0
            {
                let dev_info:Value = serde_json::from_str(&output.stdout).map_err(|e|DeviceError::LsblkError(e.to_string()))?;

                if let Value::Array(blockdevices) = &dev_info["blockdevices"]
                {
                    if blockdevices.len()==1
                    {
                        let dev = &blockdevices[0];
                        let name:String = dev["name"].as_str().unwrap().to_string();
                        let model:String = dev["model"].as_str().unwrap().to_string();
                        let serial:String = dev["serial"].as_str().unwrap().to_string();
                        let size:u64 = match &dev["size"]
                        {
                            Value::Number(sz) => sz.as_u64().unwrap(),
                            _ => unreachable!()
                        };

                        let paths = get_dev_paths(&name).await;

                        

                        return Ok(Device{
                            name,
                            paths: paths,
                            state,
                            model: Some(model),
                            serial_number: Some(serial),
                            size
                        });
                    }
                    else { return Err(DeviceError::LsblkError(format!("Found {} block device(s). Expected 1",blockdevices.len()))); }
                }
                else { return Err(DeviceError::LsblkError("Unexpected output format".to_string())); }
            }
            return Err(DeviceError::LsblkError(output.stderr));
        }
        
        return Err(DeviceError::LsblkError(String::new()));
                
    }

    pub async fn from_subpath(subpath:&str,state:DiskState) -> Result<Device,DeviceError>
    {
        let output_find = Find(
            "/dev".to_string(),
            Some(format!("*{}",subpath)),
            None,
            None,
            false,
            CmdConfig::Empty)
        .run()
        .await
        .map_err(|e| DeviceError::DeviceNotFound(e.to_string()))?
        .ok_or_else(|| DeviceError::LsblkError(format!("Found no output for {}", subpath)))?
        .is_success()
        .map_err(|e| DeviceError::DeviceNotFound(e.to_string()))?;

        for line in output_find.stdout.lines()
        {
            let dev = Device::new(line.trim(),state.clone()).await;
            if dev.is_ok() { return dev }
        }

        Err(DeviceError::DeviceNotFound(subpath.to_string()))
    }

    pub fn new_offline(path:&str) -> Device
    {
        Device
        {
            name: path.to_string(),
            paths: vec![path.to_string()],
            state: DiskState::OFFLINE,
            model: None,
            serial_number: None,
            size:0
        }
    }

    pub async fn from_lsblk(map:&Map<String,Value>) -> Option<Device>
    {
        if let Some(name) = map["name"].as_str()
        {
            Some(
                Device 
                { 
                    name: name.to_string(), 
                    paths: get_dev_paths(name).await,
                    state: DiskState::NEW, 
                    model: map["model"].as_str().map(|v| v.to_string()), 
                    serial_number: map["serial"].as_str().map(|v| v.to_string()),
                    size: match map["size"].as_number() {
                       Some(n) => n.as_u64().unwrap_or(0),
                       None => 0
                    }
                }
            )
        }
        else {None}
    }


    pub fn to_string(&self) -> String
    {
        self.paths[0].to_string()
    }
}

impl PartialEq for Device
{
    fn eq(&self, other: &Self) -> bool 
    {
        (self.model == other.model) && (self.serial_number == other.serial_number) && (self.size == other.size)
    }
}


pub async fn get_system_disks() -> Vec<Device>
{
    let result = LSBLK(LsblkProperties::default(), None, CmdConfig::Empty).run().await;
    let mut devs:Vec<Device> = Vec::new();

    if let Ok(r) = result && let Some(output) = r && output.exit_code==0
    {
        if let Ok(lsblk) = serde_json::from_str::<Value>(&output.stdout)
        {
            if let Value::Array(detected_disks) = &lsblk["blockdevices"]
            {
                for dev in detected_disks
                {
                    if let Value::Object(d) = dev
                    {
                        if ACCEPTED_TRAN_TYPES.contains(&d["tran"].as_str().unwrap())
                        {
                            if let Some(device) = Device::from_lsblk(d).await
                            {
                                devs.push(device);
                            }
                        }
                    }
                }
            }

        }
    }

    return devs;
}

// mod test
// {
//     #[allow(unused)]
//     use super::*;
//     #[allow(unused)]
//     use std::assert_eq;
//
//
//     #[test]
//     fn device_test() -> Result<(),Box<dyn std::error::Error>>
//     {
//         let sda = Device::new("/dev/sda",DiskState::ONLINE).await?;
//         assert_eq!(sda.name,"sda");
//         assert!(sda.paths.len()>1);
//         assert!(sda.model.is_some());
//         assert!(sda.serial_number.is_some());
//         assert!(sda.size>0);
//
//
//         let dev = Device::from_subpath("pci-0000:00:0d.0-ata-1", DiskState::ONLINE)?;
//
//         assert_eq!(dev.name,"sda");
//         assert!(dev.paths.len()>1);
//         assert!(dev.model.is_some());
//         assert!(dev.serial_number.is_some());
//         assert!(dev.size>0);
//
//         assert_eq!(sda,dev);
//
//         println!("{:?}",sda);
//         println!("{:?}",dev);
//
//         Ok(())
//     }
//
//     #[test]
//     fn device_lsblk_test() -> Result<(),Box<dyn std::error::Error>>
//     {
//         let lsblk = LSBLK
//             (LsblkProperties::default(), Some(&"/dev/sda".to_string()), None)
//             .run()
//             .unwrap()
//             .is_success()?;
//
//         let m:Value = serde_json::from_str(&lsblk.stdout).unwrap();
//
//         let device = Device::from_lsblk(&m.as_object().unwrap()["blockdevices"].as_array().unwrap()[0].as_object().unwrap());
//
//         let dev = device.unwrap();
//
//         assert_eq!(dev.name,"sda");
//         assert!(dev.paths.len()>1);
//         assert!(dev.model.is_some());
//         assert!(dev.serial_number.is_some());
//         assert!(dev.size>0);
//
//
//         println!("{:?}",dev);
//
//         Ok(())
//
//     }
// }