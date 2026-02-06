from dataclasses import dataclass
from typing import Optional, List, Any
from flask_babel import _

from msg import InfoMessages


@dataclass
class BackgroundTask:
    task_id:str
    running:bool
    progress:Optional[float]
    eta: Optional[int]
    pages: Optional[List[str]]
    last_update:float
    metadata:str
    detail:Any

class PoolExpansionTask(BackgroundTask):

    def __init__(this,*args,**kwargs):
        super().__init__(*args,**kwargs)

    def __str__(this):
        if (this.eta is not None):
            hours, remainder = divmod(this.eta, 3600)
            minutes, seconds = divmod(remainder, 60)

            eta = ""
            if hours > 0:
                eta = f"{hours}{_("h")} "
            if (minutes > 0):
                eta += f"{minutes}{_("m")} "
            else:
                eta += f"{seconds}{_("s")}"

            return InfoMessages.get_message(InfoMessages.I_POOL_EXPANSION_ETA, eta)

        else:
            return InfoMessages.get_message(InfoMessages.I_POOL_EXPANSION)