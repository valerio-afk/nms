from fastapi import APIRouter
from .auth import auth
from .net import net
from .pool import pool

v1 = APIRouter(prefix="/v1")
v1.include_router(auth)
v1.include_router(net)
v1.include_router(pool)