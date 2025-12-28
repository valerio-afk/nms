from .utils import NMSTask
from typing import List, Optional
import traceback

class TaskMixin:
    def __init__(this,*args,**kwargs):
        this._celery_tasks: List[NMSTask] = []
        super().__init__(*args, **kwargs)

    @property
    def get_tasks(this) -> List[NMSTask]:
        return [t for t in this._celery_tasks]

    @property
    def blocked_pages(this):
        return [t.page for t in this._celery_tasks if (not t.completed) and (t.page is not None)]

    def append_task(this,task):
        this._celery_tasks.append(task)

    def get_tasks_by_path(this,path:str) -> List[NMSTask]:
        path = path.lower()
        return [ t for t in this._celery_tasks if (not t.completed ) and path.startswith(t.page.lower()) ]

    def get_task_by_id(this,task_id:str) -> Optional[NMSTask]:
        for t in this._celery_tasks:
            if t.task_id == task_id:
                return t

        return None

    def get_completed_tasks(this, path=None):
        completed = []

        for t in this._celery_tasks:
            if t.completed and ((path is None) or path.lower().startswith(t.page.lower())):
                completed.append(t)

        return completed

    def remove_completed_tasks(this):
        this._celery_tasks = [t for t in this._celery_tasks if not t.completed]