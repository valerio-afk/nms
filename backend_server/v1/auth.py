from enum import Enum

import jwt
import pyotp
import pytz
import os
from datetime import datetime,timedelta
from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Any, Dict
from backend_server.utils.config import CONFIG
from backend_server.utils.responses import OTPVerification, ErrorMessage
from nms_shared import ErrorMessages

auth = APIRouter(prefix='/auth',tags=['auth'])
SECRET_KEY = os.environ.get("NMS_SECRET_KEY")



bearer = HTTPBearer()

def create_token(purpose:str, duration:int) -> str:
    released = datetime.now(pytz.timezone("UTC"))
    expire =  released + timedelta(minutes=duration)
    exp_timestamp = expire.timestamp()

    payload = {"purpose":purpose,"released": released.timestamp(), "exp":exp_timestamp}


    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    CONFIG.add_issued_token(encoded_jwt, exp_timestamp)
    return encoded_jwt

def verify_token_factory(requested_purpose:str='login'):
    def verify_token(credentials:HTTPAuthorizationCredentials = Depends(bearer)) -> Dict[str,Any]:
        token = credentials.credentials

        try:
            if (token not in CONFIG.issued_tokens):
                raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_REVOKED.name))

            payload = jwt.decode(token, SECRET_KEY, algorithms="HS256")

            purpose = payload.get("purpose")
            if (purpose is None):
                CONFIG.error("Token missing purpose claim")
                raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_MALFORMED.name))
            elif (purpose != requested_purpose):
                CONFIG.error("Purpose claim not matching")
                raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_INVALID.name))

            exp = payload.get("exp")

            if (exp is None):
                CONFIG.error("Expiration claim not matching")
                raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_MALFORMED.name))
            elif (datetime.now(pytz.timezone("UTC")).timestamp() > exp):
                CONFIG.error("Token Expired")
                raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_EXPIRED.name))

            payload['token'] = token

            return payload

        except jwt.PyJWTError:
            raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_MALFORMED.name))

    return verify_token

class AuthProperty(BaseModel):
    property:str
    value: Any

class AuthProperties(Enum):
    is_configured = 'is_configured'

@auth.get("/otp/get/{prop}", response_model=AuthProperty, responses={404: {"description": "Invalid property"}})
def auth_get_property(prop:AuthProperties) -> AuthProperty:
    match prop:
        case AuthProperties.is_configured:
            CONFIG.info(f"Requesting auth property {prop}")
            return AuthProperty(property=prop.value,value=CONFIG.is_otp_configured)
        case _:
            CONFIG.error(f"Requested invalid auth property {prop}")
            raise HTTPException(status_code=404, detail=f"Property {prop} not valid for auth")


class AuthUri(BaseModel):
    provisioning_uri: str

@auth.get("/otp/new",response_model=AuthUri,responses={403: {"description": "OPT Secret already configured"}})
def auth_new_secret() -> AuthUri:
    if (CONFIG.is_otp_configured):
        CONFIG.error("OTP is already configured")
        raise HTTPException(status_code=403, detail="You have already configured an OTP")

    secret = pyotp.random_base32()
    CONFIG.temporary_otp_secret = secret

    CONFIG.info("New OTP secret generated")

    totp = pyotp.TOTP(secret)

    uri = totp.provisioning_uri(
        name="OTP",
        issuer_name="NMS"
    )

    return AuthUri(provisioning_uri=uri)

class AuthToken(BaseModel):
    token:str

@auth.post("/otp/verify",response_model=AuthToken,responses={403: {"description": "Invalid token/OTP not configured"}})
def auth_otp_verify(data:OTPVerification) -> AuthToken:
    if (not CONFIG.is_otp_configured):
        if (CONFIG.temporary_otp_secret is not None):
            CONFIG.info("OPT Secret saved")
            CONFIG.save_otp_secret()
        else:
            CONFIG.error("OTP not configured yet")
            raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_NOT_CONF.name))

    secret = CONFIG.otp_secret

    totp = pyotp.TOTP(secret)

    if not totp.verify(data.otp):
        CONFIG.error("Invalid OTP")
        raise HTTPException(status_code=403, detail=ErrorMessage(code=ErrorMessages.E_AUTH_WRONG_OTP.name))

    token = create_token(data.purpose,data.duration)
    CONFIG.info("Valid OTP - token issued")

    return AuthToken(token=token)

@auth.get("/refresh",response_model=AuthToken,responses={403: {"description": "Invalid token"}},summary="Refresh access token")
def auth_token_refresh(token:Dict[str,Any] = Depends(verify_token_factory())) -> AuthToken:
    print(token)
    duration = (token['exp'] - token['released']) // 60
    CONFIG.revoke_token(token['token'])
    token = create_token(token["purpose"],duration)
    CONFIG.info("Auth token refreshed")

    return AuthToken(token=token)

@auth.post("/logout")
def auth_token_refresh(token:dict = Depends(verify_token_factory())) -> None:
    CONFIG.revoke_token(token['token'])