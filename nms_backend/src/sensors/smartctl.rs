use std::path::PathBuf;
use async_trait::async_trait;
use serde_json::Value;
use crate::cmdl::{CmdConfig, Executable};
use crate::cmdl::utils::{Smartctl, SmartctlActions};
use crate::sensors::{Sensor, SensorDriver, SensorMetric, SensorType, DriverRegistration};
use tokio::fs;
use tokio_stream::{StreamExt, wrappers::ReadDirStream};


pub struct SmartCtlDriver{}

pub async fn get_disks() -> std::io::Result<Vec<PathBuf>> {
    let mut disks:Vec<PathBuf> = Vec::new();

    let dirs= fs::read_dir("/sys/block").await?;
    let mut stream = ReadDirStream::new(dirs);

    while let Some(entry) =stream.next().await
    {
        if let Ok(dir_entry) = entry
        {
            let name = dir_entry.file_name().into_string().unwrap();

            let type_path = format!("/sys/block/{}/device/type", name);

            // Only include SCSI type 0 devices (direct-access disks)
            if let Ok(device_type) = fs::read_to_string(type_path).await
            {
                if device_type.trim() == "0"
                {
                    disks.push(dir_entry.path());
                }
            }
        }
    }

    Ok(disks)
}
#[async_trait]
impl SensorDriver for SmartCtlDriver
{
    async fn get_sensors(&self) -> Vec<Sensor>
    {
        let mut sensors: Vec<Sensor> = Vec::new();

        for device in get_disks().await.unwrap_or_else(|_| Vec::new())
        {
            let fname = device.file_name();
            if let Some(path) = device.to_str() && let Some(nm) = fname && let Some(name) = nm.to_str()
            {
                if let Ok(Some(output)) = Smartctl(path, SmartctlActions::List, CmdConfig::default()).run().await
                {
                    let json:Value = serde_json::from_str(output.stdout.as_str()).unwrap_or(Value::Null);

                    if let Some(obj) = json.as_object() &&
                        let Some(temp) = obj.get("temperature") &&
                        let Some(current) = temp.get("current") &&
                        let Some(value) = current.as_f64()
                    {
                        sensors.push(
                            Sensor {
                                device: SensorType::Hdd,
                                name: name.to_string(),
                                value: value as f32,
                                metric: SensorMetric::Celsius
                            }
                        )
                    }
                }
            }
        }

        sensors
    }
}

inventory::submit! {
    DriverRegistration {
        driver: || Box::new(SmartCtlDriver{}),
    }
}