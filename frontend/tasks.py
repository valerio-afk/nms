from celery import shared_task
from . import BACKEND


@shared_task()
def create_pool(pool,dataset, redundancy, encryption,compression,disks) -> str:
    BACKEND.create_pool(pool,dataset, redundancy, encryption,compression,disks)

    return "Disk array created successfully."

@shared_task()
def apt_get_updates() -> str:
    BACKEND.get_apt_updates()
    return "System update retrieved successfully."

@shared_task()
def apt_get_upgrade() -> str:
    BACKEND.get_apt_upgrade()
    return "System update completed successfully."

@shared_task(bind=True)
def expand_pool(self, new_device):
    BACKEND.expand_pool(new_device)

    done = False

    while not done:
        perc,time,success = BACKEND.get_array_expansion_status

        if (perc is None) or (time is None):
            raise Exception("Unable to get array expansion status")
        else:
            self.update_state(state="PROGRESS", meta={"current":perc,"eta":time})
            done = success

    return "Disk array expanded successfully."

