from celery import shared_task
from celery.result import  AsyncResult
from backend import  BACKEND
from typing import Optional

class NMSTask:

    def __init__(this, task_id:str, page:Optional[str]=None):
        this._task_id = task_id
        this._page = page

    @property
    def page(this):
        return this._page

    @property
    def task_id(this):
        return this._task_id

    @property
    def completed(this):
        return AsyncResult(this.task_id).ready()

    @property
    def successful(this):
        return AsyncResult(this.task_id).successful()

    @property
    def failed(this):
        return AsyncResult(this.task_id).failed()

    @property
    def result(this):
        return AsyncResult(this.task_id).result




@shared_task()
def create_pool(redundancy, encryption,compression):
    BACKEND.create_pool(redundancy, encryption,compression)

    return "Disk array created successfully."