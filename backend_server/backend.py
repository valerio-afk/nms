from .v1.api import v1
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from nms_shared.utils import setup_logger
from .utils.responses import ErrorMessage

app = FastAPI()

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