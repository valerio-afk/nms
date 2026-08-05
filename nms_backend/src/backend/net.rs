
use serde::{Serialize, Deserialize, Serializer, Deserializer};
use std::net::{Ipv4Addr, Ipv6Addr};
use crate::cmdl::net::{NMCLIDevice, NMCLIConnection};
use crate::cmdl::coreutils::Cat;
use crate::cmdl::{Executable, CmdConfig};
use regex::{Regex, Captures};
use std::collections::HashMap;
use anyhow::Error;
use ipnet::{Ipv4Net, Ipv6Net};
use configparser::ini::Ini;
use crate::backend::{propagate_error, HTTPMessage};
use crate::backend::msg::{ErrorMessages, StatusMessage};

const WIREGUARD_CONF:&'static str = "/etc/wireguard/wg0.conf";
const IFACE_TYPE_TO_SKIP: [&'static str;2] = ["loopback","bridge"];

#[derive(Debug)]
pub enum Host
{
    IPv4(Ipv4Addr),
    IPv6(Ipv6Addr),
    Name(String)
}

impl Serialize for Host 
{
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        match self 
        {
            Host::IPv4(addr) => serializer.serialize_str(&addr.to_string()),
            Host::IPv6(addr) => serializer.serialize_str(&addr.to_string()),
            Host::Name(name) => serializer.serialize_str(name),
        }
    }
}

impl<'de> Deserialize<'de> for Host 
{
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;

        if let Ok(addr) = s.parse::<Ipv4Addr>() 
        {
            Ok(Host::IPv4(addr))
        } 
        else if let Ok(addr) = s.parse::<Ipv6Addr>() 
        {
            Ok(Host::IPv6(addr))
        } 
        else 
        {
            Ok(Host::Name(s))
        }
    }
}

#[derive(Debug,Serialize,Deserialize)]
pub struct IPv4
{
    pub dynamic: bool,
    pub address: Option<Ipv4Addr>,
    pub netmask: Option<Ipv4Addr>,
    pub gateway: Option<Ipv4Addr>,
    pub dns: Vec<Host>
}

impl Default for IPv4
{
    fn default() -> Self 
    {
        IPv4 
        { 
            dynamic: false, 
            address: None,
            netmask: None,
            gateway: None,
            dns: vec![]
        }    
    }
}

#[derive(Debug,Serialize,Deserialize)]
pub struct IPv6
{
    enabled: bool,
    dynamic: bool,
    address: Option<Ipv6Addr>,
    netmask: Option<Ipv6Addr>,
    gateway: Option<Ipv6Addr>,
    
    dns: Vec<Host>
}

impl Default for IPv6
{
    fn default() -> Self 
    {
        IPv6 
        {
            enabled: false, 
            dynamic: false, 
            address: None,
            netmask: None,
            gateway: None,
            dns: vec![]
        }    
    }
}

#[derive(Debug,Serialize,Deserialize)]
#[serde(rename_all="lowercase")]
pub enum IfaceType
{
    ETHERNET,
    WIFI,
    VPN,
    UNKNOWN
}

#[derive(Debug,Serialize,Deserialize)]
pub struct NetworkInterface
{
    pub name: String,
    pub enabled: bool,
    pub ipv4: Option<IPv4>,
    pub ipv6: Option<IPv6>,
    pub network_name: String,

    #[serde(rename="type")]
    pub iface_type: IfaceType,
    pub has_profile:bool,
    pub ap:Option<bool>    
}


pub async fn get_network_ifaces() -> Vec<NetworkInterface>
{
    let mut ifaces: Vec<NetworkInterface> = Vec::new();
    let nmcli_dev_output = NMCLIDevice("status", None, CmdConfig::Empty).run().await;

    if let Ok(r) = nmcli_dev_output && let Some(output) = r && (output.exit_code==0)
    {
        for l in output.stdout.lines().map(|s| s.split(":").collect::<Vec<&str>>())
        {
            
            if l.len() != 4 { continue; }
            let iface = l[0].trim();
            let tpe = l[1].trim();
            let state = l[2].trim();
            let connection = l[3].trim();


            if IFACE_TYPE_TO_SKIP.contains(&tpe) || state.contains("unmanaged") { continue; }

            let mut hotspot:Option<bool> = None;

            let iface_type:IfaceType = match tpe
            {
                "ethernet" => IfaceType::ETHERNET,
                "wifi" => {
                    hotspot = Some(if connection.contains("Hotspot") {true} else {false});
                    IfaceType::WIFI
                }
                _ => continue
            };

            let iface_enabled:bool = if state.starts_with("connected") {true} else {false};
            let mut ipv4_info:Option<IPv4> = None;
            let mut ipv6_info:Option<IPv6> = None;
            let mut has_profile = false;

            

            if iface_enabled
            {
                let args:Option<&[&str]> = Some(&[connection]);
                let nmcli_conn_output = NMCLIConnection("show", args, CmdConfig::Empty).run().await;

                if let Ok(r) = nmcli_conn_output && let Some(output2) = r && (output2.exit_code==0)
                {
                    
                    ipv4_info = Some(IPv4::default());
                    ipv6_info = Some(IPv6::default());
                    has_profile = true;

                    for line in output2.stdout.lines()
                    {
                        
                        let tok = line.split(":").collect::<Vec<&str>>();

                        let property = tok[0].trim();
                        let value = if tok.len() == 2 {Some(tok[1].trim())} else {None};

                        match property
                        {
                            "ipv4.method" => if let Some(v) = value && (v!="manual") {ipv4_info.as_mut().map(|v| v.dynamic=true);}
                            "ipv4.addresses" => if let Some(v)  = value && (v.len()>0)
                                {
                                    if let Ok(ip) = v.parse::<Ipv4Net>()
                                    {
                                        ipv4_info.as_mut().map(|v| {
                                            v.address = Some(ip.addr());
                                            v.netmask = Some(ip.netmask());
                                        });
                                    }
                                }
                            
                            "ipv4.gateway" => if let Some(v) = value && (v.len()>0)
                                {
                                    if let Ok(gateway) = v.parse::<Ipv4Addr>()
                                    {
                                        ipv4_info.as_mut().map(|v| v.gateway=Some(gateway));
                                    }
                                }
                            "ipv4.dns" => if let Some(v) = value
                            {
                                let mut dns_addr:Vec<Host> = Vec::new();

                                for addr in v.split(",")
                                {
                                    if let Ok(dns_ip) = addr.parse::<Ipv4Addr>()
                                    {
                                        dns_addr.push(Host::IPv4(dns_ip));
                                    }
                                    else if addr.len() > 0
                                    {
                                        dns_addr.push(Host::Name(addr.to_string()));
                                    }
                                }

                                ipv4_info.as_mut().map(|v| v.dns=dns_addr);
                            }
                            "ipv6.method" => if let Some(v) = value
                            {
                                if v!="manual" {ipv6_info.as_mut().map(|v| v.dynamic=true);}
                                if (v!="disabled") || (v!="ignore") {ipv6_info.as_mut().map(|v| v.enabled=true);}

                            }
                            "IP6.ADDRESS[1]" => if let Some(v) = value && (v.len()>0)
                            {
                                let ip6 = v.parse::<Ipv6Net>();

                                if let Ok(ip) = ip6
                                {
                                    ipv6_info.as_mut().map(|v| {
                                        v.address = Some(ip.addr());
                                        v.netmask = Some(ip.netmask());
                                    });
                                }
                            }
                            "IP6.GATEWAY" => if let Some(v) = value && (v.len()>0)
                            {
                                if let Ok(gateway) = v.parse::<Ipv6Addr>()
                                {
                                    ipv6_info.as_mut().map(|v| v.gateway=Some(gateway));
                                }

                            } 
                            "ipv6.dns" => if let Some(v) = value
                            {
                                let mut dns_addr:Vec<Host> = Vec::new();

                                for addr in v.split(",")
                                {
                                    if let Ok(dns_ip) = addr.parse::<Ipv6Addr>()
                                    {
                                        dns_addr.push(Host::IPv6(dns_ip));
                                    }
                                    else if addr.len() > 0
                                    {
                                        dns_addr.push(Host::Name(addr.to_string()));
                                    }
                                }

                                ipv6_info.as_mut().map(|v| v.dns=dns_addr);
                            }
                            _ => if let Some(v) = value && (v.contains("="))
                            {
                                let tok = v.split("=").collect::<Vec<&str>>();
                                if tok.len() == 2
                                {
                                    let sub_property = tok[0].trim();
                                    let sub_value = tok[1].trim();

                                    match sub_property
                                    {
                                        "ip_address" => if let Ok(ip) = sub_value.parse::<Ipv4Addr>()
                                        {
                                            ipv4_info.as_mut().map(|v| v.address = Some(ip));
                                        }
                                        "subnet_mask" => if let Ok(ip) = sub_value.parse::<Ipv4Addr>()
                                        {
                                            ipv4_info.as_mut().map(|v| v.netmask = Some(ip));
                                        }
                                        "domain_name_servers" => if let Ok(ip) = sub_value.parse::<Ipv4Addr>()
                                        {
                                            ipv4_info.as_mut().map(|v| v.dns.push(Host::IPv4(ip)));
                                        }
                                        "routers" => if let Ok(ip) = sub_value.parse::<Ipv4Addr>()
                                        {
                                            ipv4_info.as_mut().map(|x| x.gateway = Some(ip));
                                        }
                                        _ => ()
                                    }
                                }
                            }
                            // _ => todo!()
                        }
                    }
                }
            }


            ifaces.push(NetworkInterface { 
                name: iface.to_string(), 
                enabled: iface_enabled, 
                ipv4: ipv4_info, 
                ipv6: ipv6_info, 
                network_name: connection.to_string(), 
                iface_type: iface_type, 
                has_profile,
                ap: hotspot 
            });

        }
    }

    return ifaces;

}

pub async fn read_wireguard_config_file() -> Result<Ini, HTTPMessage>
{
    let output = Cat(
        Some(WIREGUARD_CONF.to_string()),
        CmdConfig::default()
    ).run()
    .await
    .map_err(|e| propagate_error(ErrorMessages::E_NET_VPN_CONF,e))?
    .ok_or_else(|| ErrorMessages::E_NET_VPN_CONF.wrap_with_status_code(None))?;


    let re = Regex::new(r"\[(.*?)\]").map_err(|e| propagate_error(ErrorMessages::E_NET_VPN_CONF,e))?;

    let mut counts: HashMap<String,u32> = HashMap::new();

    let cfg = re.replace_all(&output.stdout,|c:&Captures|
    {
        let name = c[1].to_string();
        if let Some(v) = counts.get(&name) { counts.insert(name.clone(), v+1); }
        else { counts.insert(name.clone(), 1); }

        if name.to_lowercase() == "peer" { format!("[{}@{}]",name,counts.get(&name).unwrap()) }
        else { format!("[{}]",name) }
    });

    let mut cfg_parser = Ini::new();
    cfg_parser.read(cfg.to_string()).map_err(|e| propagate_error(ErrorMessages::E_NET_VPN_CONF,Error::msg(e)))?;

    Ok(cfg_parser)
}