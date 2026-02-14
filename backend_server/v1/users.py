from backend_server.utils.config import CONFIG
from backend_server.utils.responses import UserProfile
from backend_server.v1.auth import verify_token_factory
from fastapi import APIRouter, Depends
from typing import List,Optional

verify_token = verify_token_factory()

users = APIRouter(
    prefix='/users',
    tags=['users'],
    dependencies=[Depends(verify_token)]
)


@users.get("/get",response_model=Optional[UserProfile],summary="Get the information of the logged user")
def get_user(token:dict=Depends(verify_token)) -> Optional[UserProfile]:
    return CONFIG.get_user(token.get("username"))


