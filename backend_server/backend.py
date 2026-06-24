from .utils.responses import ErrorMessage, WarningMessage
from .v1.api import v1
from backend_server.utils.limiter import limiter
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from logging import getLogger
from nms_shared import ErrorMessages
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


__version__ = "0.1rc1"

@asynccontextmanager
async def automount(app:FastAPI):
    from backend_server.utils.config import CONFIG
    from backend_server.v1.pool import mount
    if ((CONFIG.is_pool_configured) and (not CONFIG.is_mounted)):
        CONFIG.info("Start up automount")
        try:
            mount()
        except HTTPException as e:
            ... # something went wrong

    yield

app = FastAPI(lifespan=automount,root_path="/api",title="NMS",version=__version__)



app.include_router(v1)

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

# Custom exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail

    logger = getLogger("nms.backend")

    logger.error(
        f"Exception on {request.method} {request.url} -> {exc.detail}",
        exc_info=exc
    )

    if isinstance(detail, (ErrorMessage,WarningMessage)):
        detail = detail.model_dump()
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail},
        headers=exc.headers
    )

@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):

    logger = getLogger("nms.backend")

    logger.error(
        f"Exception on {request.method} {request.url}",
        exc_info=exc
    )
    return JSONResponse(
        status_code=500,
        content={"detail": {"code":ErrorMessages.E_UNKNOWN.name}}
    )