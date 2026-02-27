from enum import Enum
import jwt
import pyotp
import pytz
import os
from datetime import datetime,timedelta
from fastapi import APIRouter, HTTPException, Request
from fastapi.params import Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Any, Dict, Optional
from backend_server.utils.config import CONFIG
from backend_server.utils.responses import OTPVerification, ErrorMessage, AuthToken, Token
from nms_shared import ErrorMessages
from nms_shared.enums import UserPermissions

auth = APIRouter(prefix='/auth',tags=['auth'])
SECRET_KEY = os.environ.get("NMS_SECRET_KEY")



bearer = HTTPBearer()


def check_permission(username:str, perm:UserPermissions) -> None:
    if (not CONFIG.has_user_permission(username,perm)):
        raise HTTPException(status_code=401,detail=perm.value)

def create_token(username:str,purpose:str, duration:int) -> str:
    released = datetime.now(pytz.timezone("UTC"))
    expire =  released + timedelta(minutes=duration)
    exp_timestamp = expire.timestamp()

    payload = {"username":username,"purpose":purpose,"released": released.timestamp(), "exp":exp_timestamp}

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    CONFIG.add_issued_token(encoded_jwt, exp_timestamp)
    return encoded_jwt

def token_verification(token:str,requested_purpose:str) -> Dict[str, Any]:
    try:


        payload = jwt.decode(token, SECRET_KEY, algorithms="HS256")

        purpose = payload.get("purpose")
        if (purpose is None):
            CONFIG.error("Token missing `purpose` claim")
            raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_MALFORMED.name))
        elif (purpose != requested_purpose):
            CONFIG.error(f"Purpose claim not matching ({purpose} != {requested_purpose})")
            raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_INVALID.name))

        if ( (purpose != "first_login") and (token not in CONFIG.issued_tokens)):
            raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_REVOKED.name))

        exp = payload.get("exp")

        if (exp is None):
            CONFIG.error("Token missing `expiration` claim")
            raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_MALFORMED.name))
        elif (datetime.now(pytz.timezone("UTC")).timestamp() > exp):
            CONFIG.error("Token Expired")
            raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_EXPIRED.name))

        payload['token'] = token

        return payload

    except jwt.PyJWTError:
        raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_MALFORMED.name))

def verify_token_factory(requested_purpose:str='login'):
    def verify_token(credentials:HTTPAuthorizationCredentials = Depends(bearer)) -> Dict[str,Any]:
        token = credentials.credentials

        return token_verification(token,requested_purpose)

    return verify_token

def verify_token_header_factory(requested_purpose:str):
    def verify_token(request: Request) -> Dict[str,Any]:
        header_name = f"X-Extra-Auth-{requested_purpose}"

        try:
            token = request.headers[header_name]
            return token_verification(token, requested_purpose)
        except KeyError:
            CONFIG.error(request.headers)
            raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_INVALID.name))

    return verify_token


class AuthProperty(BaseModel):
    property:str
    value: Any

class AuthProperties(Enum):
    is_configured = 'is_configured'
    is_new_otp_ready = 'is_new_otp_ready'

@auth.get("/otp/get/{prop}", response_model=AuthProperty, responses={404: {"description": "Invalid property"}})
def auth_get_property(prop:AuthProperties) -> AuthProperty:
    result = None
    match prop:
        case AuthProperties.is_configured:
            result = AuthProperty(property=prop.value,value=CONFIG.is_otp_configured)
        # case AuthProperties.is_new_otp_ready:
        #     result = AuthProperty(property=prop.value, value=CONFIG.temporary_otp_secret is not None)
        case _:
            CONFIG.error(f"Requested invalid auth property {prop}")
            raise HTTPException(status_code=404, detail=f"Property {prop} not valid for auth")

    CONFIG.info(f"{result.property}={result.value}")
    return result


class AuthUri(BaseModel):
    provisioning_uri: str

@auth.get("/otp/new",response_model=AuthUri,responses={403: {"description": "OPT Secret already configured"}})
def auth_new_secret(token:Optional[str]=Query(default=None)) -> AuthUri:
    if ((token is None) and CONFIG.is_otp_configured):
        CONFIG.error("OTP is already configured")
        raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_ALREADY_CONFIG.name))

    username = None

    if (token is not None):
        token_data = token_verification(token,"first_login")
        username = token_data["username"]
        if (CONFIG.is_otp_configured_for(username)):
            raise HTTPException(status_code=401)

    secret = pyotp.random_base32()
    CONFIG.set_temporary_otp_secret(username,secret)

    CONFIG.info("New OTP secret generated")

    totp = pyotp.TOTP(secret)

    uri = totp.provisioning_uri(
        name="OTP",
        issuer_name="NMS"
    )

    return AuthUri(provisioning_uri=uri)



@auth.post("/otp/verify",response_model=AuthToken,responses={403: {"description": "Invalid token/OTP not configured"}})
def auth_otp_verify(data:OTPVerification) -> AuthToken:
    # if (not CONFIG.is_otp_configured):
    #     if (CONFIG.temporary_otp_secret is not None):
    #         CONFIG.info("OPT Secret saved")
    #         CONFIG.save_otp_secret()
    #     else:
    #         CONFIG.error("OTP not configured yet")
    #         raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_NOT_CONF.name))

    # check first if there are any temporary secrets, ie someone is attempting their first login
    temp_secrets = CONFIG.temporary_otp_secrets

    username = None

    for uname,secret in temp_secrets.items():
        totp = pyotp.TOTP(secret)
        if (totp.verify(data.otp)):
            username = CONFIG.save_temporary_otp(uname)
            break



    if (username is None):
        secrets = CONFIG.otp_secrets

        for uname,secret in secrets.items():
            totp = pyotp.TOTP(secret)
            if (totp.verify(data.otp)):
                username = uname
                break

    if username is None:
        CONFIG.error("Invalid OTP")
        raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_WRONG_OTP.name))


    check_permission(username, UserPermissions.CLIENT_DASHBOARD_ACCESS)

    token = create_token(username,data.purpose,data.duration)
    CONFIG.info(f"Valid OTP for `{username}` - token issued")

    return AuthToken(token=token,username=username)

# @auth.post("/otp/reset",responses={403: {"description": "Invalid token"}},summary="Reset the OTP secret")
# def auth_token_refresh(token:Dict[str,Any] = Depends(verify_token_factory())) -> None:
#     CONFIG.revoke_token(token['token'])
#     CONFIG.otp_secret = None
#     CONFIG.warning("OTP secret reset")


@auth.get("/refresh",response_model=AuthToken,responses={403: {"description": "Invalid token"}},summary="Refresh access token")
def auth_token_refresh(token:Dict[str,Any] = Depends(verify_token_factory())) -> AuthToken:
    duration = (token['exp'] - token['released']) // 60
    CONFIG.revoke_token(token['token'])
    username = token['username']
    token = create_token(username,token["purpose"],duration)
    CONFIG.info(f"Auth token refreshed for `{username}`")

    return AuthToken(token=token,username=username)

@auth.post("/logout")
def auth_logout(token:dict = Depends(verify_token_factory())) -> None:
    CONFIG.revoke_token(token['token'])
    CONFIG.info(f"`{token['username']}` has logged out")

@auth.get("/token/first_login")
def auth_first_login(token:Optional[str]=Query(default=None)) -> bool:
    try:
        payload = token_verification(token,"first_login")
        return CONFIG.is_otp_configured_for(payload["username"])

    except HTTPException:
        return False