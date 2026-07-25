use std::unreachable;
use strum::{EnumString, FromRepr};
use serde::Serialize;
use serde_json::{Value};
use crate::cmdl::Executable;
use crate::cmdl::utils::Find;
use crate::cmdl::utils::{LSBLK, LsblkProperties,UdevAdmInfo};

#[derive(Debug, Serialize,FromRepr, PartialEq,EnumString, Clone)]
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

#[derive(Debug, Serialize)]
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



impl Device
{
    pub fn new(path:&str,state:DiskState) -> Result<Device,DeviceError>
    {
        if let Some(output) = LSBLK(
            LsblkProperties::default(), 
                  Some(&path.to_string()), 
                None
            ).run()
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

                        let  mut paths:Vec<String> = vec![dev["path"].as_str().unwrap().to_string()];

                        if let Some(udev_output) = UdevAdmInfo(&name, Some("symlink"), None).run()
                        {
                            if udev_output.exit_code == 0
                            {
                                for d in udev_output.stdout.trim().split(" ")
                                {
                                    paths.push(format!("/dev/{}",d));
                                }
                            }
                        }

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

    pub fn from_subpath(subpath:&str,state:DiskState) -> Result<Device,DeviceError>
    {
        let output_find = Find(
            "/dev".to_string(),
            Some(format!("*{}",subpath)),
            None,
            None,
            false,
            None)
        .run()
        .unwrap()
        .is_success()
        .map_err(|e| DeviceError::DeviceNotFound(e.to_string()))?;

        for line in output_find.stdout.lines()
        {
            let dev = Device::new(line.trim(),state.clone());
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


mod test
{
    #[allow(unused)]
    use super::*;
    #[allow(unused)]
    use std::assert_eq;
    

    #[test]
    fn device_test() -> Result<(),Box<dyn std::error::Error>>
    {
        let sda = Device::new("/dev/sda",DiskState::ONLINE)?;
        assert_eq!(sda.name,"sda");
        assert!(sda.paths.len()>1);
        assert!(sda.model.is_some());
        assert!(sda.serial_number.is_some());
        assert!(sda.size>0);


        let dev = Device::from_subpath("pci-0000:00:0d.0-ata-1", DiskState::ONLINE)?;

        assert_eq!(sda.name,"sda");
        assert!(sda.paths.len()>1);
        assert!(sda.model.is_some());
        assert!(sda.serial_number.is_some());
        assert!(sda.size>0);

        assert_eq!(sda,dev);

        Ok(())
    }
}