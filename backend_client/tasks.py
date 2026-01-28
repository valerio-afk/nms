from .utils import NMSTask
from typing import List, Optional


class TaskMixin:
    @property
    def get_tasks(this) -> List[NMSTask]:
        ...

    @property
    def blocked_pages(this):
        ...

    def append_task(this,task):
        ...

    def get_tasks_by_path(this,path:str) -> List[NMSTask]:
        ...

    def get_task_by_id(this,task_id:str) -> Optional[NMSTask]:
        ...

    def get_completed_tasks(this, path=None):
        ...

    def remove_completed_tasks(this):
        ...