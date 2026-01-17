from fastapi import FastAPI
from v1.api import v1
from nms_utils import setup_logger

app = FastAPI()

app.include_router(v1)

setup_logger(__name__)