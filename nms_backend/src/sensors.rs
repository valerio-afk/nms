use async_trait::async_trait;
use serde::Serialize;
use inventory;

mod lmsensors;
mod smartctl;
mod rpi_sensors;

inventory::collect!(DriverRegistration);

#[derive(Serialize)]
#[serde(rename_all = "lowercase")]
pub enum SensorType
{
    Cpu,
    Hdd,
    Fan,
}
#[derive(Serialize)]
pub enum SensorMetric
{
    #[serde(rename = "°C")]
    Celsius,
    #[serde(rename = "RPM")]
    Rpm,
    #[serde(rename = "V")]
    Volt,
}


#[derive(Serialize)]
pub struct Sensor
{
    device: SensorType,
    name: String,
    value: f32,
    metric: SensorMetric,
}

#[async_trait]
pub trait SensorDriver: Send + Sync
{
    async fn get_sensors(&self) -> Vec<Sensor>;
}

pub struct DriverRegistration
{
    pub driver: fn() -> Box<dyn SensorDriver>,
}

pub async fn get_sensors() -> Vec<Sensor>
{
    let mut sensors = Vec::new();
    for reg in inventory::iter::<DriverRegistration>
    {
        let driver = (reg.driver)();
        sensors.extend(driver.get_sensors().await);
    }

    sensors
}