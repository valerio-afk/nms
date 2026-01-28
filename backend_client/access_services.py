from typing import  Dict

class AccessServicesMixin:
    @property
    def get_access_services(this) -> Dict[str, dict]    :
        ...

    def disable_all_access_services(this) -> None:
        ...
