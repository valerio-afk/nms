from typing import Optional, List, Dict
import datetime

class SystemMixin:
    @property
    def system_information(this) -> Dict[str, str]:
        ...

    @property
    def get_updates(this) -> List[str]:
        ...

    def reboot(this) -> None:
        ...

    def shutdown(this) -> None:
        ...

    def restart_systemd_services(this) -> None:
        ...



    def get_apt_updates(this) -> None:
        ...


    def get_apt_upgrade(this) -> None:
        ...

    def last_apt_time(this) -> Optional[datetime.datetime]:
        ...
