from dataclasses import dataclass
from typing import Optional
from enum import  Enum

@dataclass(frozen=True)
class NetworkInterface:
    name:str
    status:bool
    ipv4:str
    ipv6: str
    network_name:Optional[str]