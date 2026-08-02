use async_trait::async_trait;
use crate::cmdl::{CmdConfig, Executable};
use crate::cmdl::rpi::{VCGENCMD, VideoCoreCommands};
use crate::sensors::{Sensor, SensorDriver, SensorMetric, SensorType, DriverRegistration};
use crate::rpi::is_raspberry_pi;

pub struct RPiDriver{}
#[async_trait]
impl SensorDriver for RPiDriver
{
    async fn get_sensors(&self) -> Vec<Sensor>
    {
        let mut sensors: Vec<Sensor> = Vec::new();

        if is_raspberry_pi().await
        {
            if let Ok(Some(output)) = VCGENCMD(VideoCoreCommands::MEASURE_TEMP,CmdConfig::default()).run().await &&
                output.exit_code == 0
            {
                let tokens = output.stdout.split('=').collect::<Vec<&str>>();

                if tokens.len() >=2 && tokens[1].len()>0
                {
                    let v = tokens[1];
                    
                    if let Ok(value) = v[..v.len()-2].parse::<f32>()
                    {
                        sensors.push(
                            Sensor {
                                device: SensorType::Cpu,
                                name: "SOC".to_string(),
                                value,
                                metric: SensorMetric::Celsius
                            }
                        )
                    }
                }
            }

            if let Ok(Some(output)) = VCGENCMD(VideoCoreCommands::MEASURE_VOLT,CmdConfig::default()).run().await &&
                output.exit_code == 0
            {
                let tokens = output.stdout.split('=').collect::<Vec<&str>>();

                if tokens.len() >=2 && tokens[1].len()>0
                {
                    let v = tokens[1];

                    if let Ok(value) = v[..v.len()-1].parse::<f32>()
                    {
                        sensors.push(
                            Sensor {
                                device: SensorType::Cpu,
                                name: "SOC".to_string(),
                                value,
                                metric: SensorMetric::Volt
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
        driver: || Box::new(RPiDriver{}),
    }
}