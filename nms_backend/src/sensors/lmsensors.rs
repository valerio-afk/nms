
use regex::Regex;
use super::{Sensor, SensorDriver, SensorType, SensorMetric, DriverRegistration};
use serde_json::{Map, Value};
use async_trait::async_trait;
use inventory;
use crate::cmdl::utils::Sensors;
use crate::cmdl::{CmdConfig, Executable};

pub struct LMSensorDriver;

impl LMSensorDriver
{
    fn parse_coretemp(&self, data:Option<&Map<String, Value>>) -> Vec<Sensor>
    {
        let mut sensors:Vec<Sensor> = Vec::new();

        if let Some(coretemp) = data
        {
            let package_re = Regex::new(r"Package id ([0-9]+)").unwrap();
            let core_re = Regex::new(r"Core ([0-9]+)").unwrap();
            let temp_re = Regex::new(r"temp[0-9]+_input").unwrap();

            for (k,v) in coretemp
            {
                let mut name:Option<String> = None;

                if let Some(pkg_captures) = package_re.captures(k) && pkg_captures.len()>=2
                {
                    let id = pkg_captures[1].parse::<i32>().unwrap();
                    name = Some(format!("CPU {}",id+1));
                }
                else if let Some(core_captures) = core_re.captures(k) && core_captures.len()>=2
                {
                    let id = core_captures[1].parse::<i32>().unwrap();
                    name = Some(format!("Core {}",id+1));
                }

                if let Some(sensor_name) = name && let Some (obj) = v.as_object()
                {
                    for (tk,tv) in obj
                    {
                        if let Some(temp) = tv.as_f64() && temp_re.is_match(tk)
                        {
                            sensors.push(
                                Sensor {
                                    device: SensorType::Cpu,
                                    name: sensor_name.clone(),
                                    value: temp as f32,
                                    metric: SensorMetric::Celsius,
                                }
                            )
                        }
                    }
                }
            }
        }

        sensors
    }

    fn parse_anyfan(&self, data:Option<&Map<String, Value>>) -> Vec<Sensor>
    {
        let mut sensors:Vec<Sensor> = Vec::new();

        if let Some(fans) = data
        {
            let fan_re = Regex::new(r"fan([0-9]+)").unwrap();

            for (k,v) in fans
            {
                if let Some(fan_captures) = fan_re.captures(k)
                {
                    let id = fan_captures[1].parse::<i32>().unwrap();
                    let name = format!("Fan {}",id+1);
                    let fan_key = format!("{}_input",k);

                    if let Some(fan) = v.as_object() &&
                        let Some (value) = fan.get(&fan_key) &&
                        let Some(rpm) = value.as_f64()
                    {

                        sensors.push(
                            Sensor {
                                device: SensorType::Fan,
                                name: name.clone(),
                                value: rpm as f32,
                                metric: SensorMetric::Rpm,
                            }
                        )
                    }
                }
            }
        }

        sensors
    }
}

#[async_trait]
impl SensorDriver for LMSensorDriver
{
    async fn get_sensors(&self) -> Vec<Sensor>
    {
        let mut sensors: Vec<Sensor> = Vec::new();

        if let Ok(Some(output)) = Sensors(CmdConfig::Empty).run().await && output.exit_code==0
        {
            let json:Value = serde_json::from_str(output.stdout.as_str()).unwrap_or(Value::Null);

            if let Some(obj) = json.as_object()
            {
                for (sensor,data) in obj
                {
                    if sensor.contains("coretemp")
                    {
                        sensors.extend(self.parse_coretemp(data.as_object()));
                    }
                    else
                    {
                        sensors.extend(self.parse_anyfan(data.as_object()));
                    }
                }
            }
        }
        sensors
    }
}

inventory::submit! {
    DriverRegistration {
        driver: || Box::new(LMSensorDriver {}),
    }
}