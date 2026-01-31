from dataclasses import dataclass
from typing import Optional, List

@dataclass
class BackgroundTask:
    task_id:str
    running:bool
    progress:Optional[float]
    eta: Optional[int]
    pages: Optional[List[str]]
    last_update:float
    metadata:str