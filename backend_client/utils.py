from celery.result import AsyncResult
from enum import Enum
from typing import Optional, Any

class NMSTask:

    def __init__(this, task_id:str,
                       page:Optional[str]=None,
                       action:Optional[str]=None,
                       tag:Optional[str]=None):
        this._task_id = task_id
        this._page = page
        this._action = action
        this._tag = tag

    @property
    def action(this) -> Optional[str]:
        return this._action

    @property
    def tag(this) -> Optional[str]:
        return this._tag

    @property
    def page(this) -> Optional[str]:
        return this._page

    @property
    def task_id(this) -> str:
        return this._task_id

    @property
    def completed(this) -> bool:
        return AsyncResult(this.task_id).ready()

    @property
    def successful(this) -> bool:
        return AsyncResult(this.task_id).successful()

    @property
    def failed(this) -> bool:
        return AsyncResult(this.task_id).failed()

    @property
    def result(this) -> AsyncResult:
        return AsyncResult(this.task_id).result

    @property
    def data(this) -> Any:
        return AsyncResult(this.task_id).info

    def __eq__(this, other:Any) -> bool:
        if (isinstance(other, NMSTask)):
            return this.task_id == other.task_id
        return False


    def __repr__(this) -> str:
        return f"NMSTask(id={this.task_id},tag={this.tag},page={this.page},action={this.action})"



class LogFilter(Enum):
    FLASK = 0
    BACKEND = 1
    CELERY = 2
    SUDODAEMON = 3


class TaskStatus(Enum):
    PROGRESS=0
    SUCCESSFUL=1
    FAILED=-1


class OwnershipHandler():
    def __init__(this,uid,gid):
        this._uid = uid
        this._gid = gid

        super().__init__()