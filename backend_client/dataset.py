from typing import Optional

class DatasetMixin:

    @property
    def dataset_name(this) -> Optional[str]:
        ...

    @property
    def mountpoint(this) -> Optional[str]:
        ...

    @property
    def is_mounted(this):
        ...

    def mount(this) -> None:
        ...



    def unmount(this) -> None:
        ...

    def simulate_format(this) -> None:
       ...