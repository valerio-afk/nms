from .v1.api import v1
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from nms_shared.utils import setup_logger
from .utils.responses import ErrorMessage
from contextlib import asynccontextmanager

@asynccontextmanager
async def automount(app:FastAPI):
    from backend_server.utils.config import CONFIG
    from backend_server.v1.pool import pool_mount
    if ((CONFIG.is_pool_configured) and (not CONFIG.is_mounted)):
        CONFIG.info("Start up automount")
        pool_mount()

    yield

app = FastAPI(lifespan=automount)

app.include_router(v1)

setup_logger(__name__)

# Custom exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, ErrorMessage):
        detail = detail.model_dump()
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail},
        headers=exc.headers
    )