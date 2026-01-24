from fastapi import APIRouter

from .acpi import acpi
from .auth import auth
from .net import net
from .pool import pool
from .disks import disks
from .fs import fs

v1 = APIRouter(prefix="/v1")
v1.include_router(auth)
v1.include_router(net)
v1.include_router(pool)
v1.include_router(disks)
v1.include_router(acpi)
v1.include_router(fs)