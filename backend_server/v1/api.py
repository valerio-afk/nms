from fastapi import APIRouter
from .system import system
from .auth import auth
from .net import net
from .pool import pool
from .disks import disks
from .fs import fs, fs_preview
from .services import services
from .users import users

v1 = APIRouter(prefix="/v1")
v1.include_router(auth)
v1.include_router(net)
v1.include_router(pool)
v1.include_router(disks)
v1.include_router(system)
v1.include_router(services)
v1.include_router(fs)
v1.include_router(fs_preview)
v1.include_router(users)