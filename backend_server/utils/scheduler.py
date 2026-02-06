import datetime
from dataclasses import dataclass

from backend_server.utils.config import CONFIG
from nms_shared.threads import NMSThread
from uuid import uuid4
from typing import Optional


@dataclass(frozen=True)
class ScheduledTask:
    thread: NMSThread
    scheduled_time: datetime.datetime

class TaskScheduler:
    LIFETIME = 3600

    def __init__(this) -> None:
        this._tasks = dict()

    def schedule(this,task:NMSThread) -> str:
        task.start()
        time = datetime.datetime.now()

        uuid = str(uuid4())

        this._tasks[uuid] = ScheduledTask(thread=task,scheduled_time=time)

        return uuid

    def get_task_by_id(this,uuid:str) -> Optional[ScheduledTask]:
        task = this._tasks.get(uuid)


        this._tasks = {uuid:task for uuid,task in this._tasks.items() if (task.thread.is_running) }

        return task

SCHEDULER = TaskScheduler()