import jwt
import pyotp
import pytz
from datetime import datetime,timedelta
from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Any, Dict
from backend_server.utils.config import CONFIG

auth = APIRouter(prefix='/auth',tags=['auth'])

class OTPVerification(BaseModel):
    purpose:str
    duration:int
    otp:str


bearer = HTTPBearer()

def create_token(data:OTPVerification) -> str:
    released = datetime.now(pytz.timezone("UTC"))
    expire =  released + timedelta(minutes=data.duration)

    payload = {"purpose":data.purpose,"released": released.timestamp(), "exp":expire.timestamp()}

    #TODO: secret must be taken from ENV
    secret_key = "test_secret_key"

    encoded_jwt = jwt.encode(payload, secret_key, algorithm="HS256")
    return encoded_jwt

def verify_token_factory(requested_purpose:str='login'):
    def verify_token(credentials:HTTPAuthorizationCredentials = Depends(bearer)) -> Dict[str,Any]:
        token = credentials.credentials

        try:
            # TODO: secret must be taken from ENV
            secret_key = "test_secret_key"

            payload = jwt.decode(token, secret_key, algorithms="HS256")

            purpose = payload.get("purpose")
            if (purpose is None):
                raise HTTPException(status_code=403, detail="Token missing purpose claim")
            elif (purpose != requested_purpose):
                raise HTTPException(status_code=403, detail="Wrong purpose claim")

            exp = payload.get("exp")

            if (exp is None):
                raise HTTPException(status_code=403, detail="Token missing expire claim")
            elif (datetime.now(pytz.timezone("UTC")).timestamp() > exp):
                raise HTTPException(status_code=403, detail="Token expired")

            return payload

        except jwt.PyJWTError:
            raise HTTPException(status_code=403, detail="Invalid Token")

    return verify_token

class AuthProperty(BaseModel):
    property:str
    value: Any

@auth.get("/otp/get/{prop}", response_model=AuthProperty, responses={404: {"description": "Invalid property"}})
def auth_get_property(prop:str) -> AuthProperty:
    match prop:
        case "is_configured":
            CONFIG.info(f"Requesting auth property {prop}")
            return AuthProperty(property=prop,value=CONFIG.is_otp_configured)
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
            CONFIG.error("OTP is already configured")
            raise HTTPException(status_code=403, detail="You have not configured the OTP secret")

    secret = CONFIG.otp_secret

    totp = pyotp.TOTP(secret)

    if not totp.verify(data.otp):
        CONFIG.error("Invalid OTP")
        raise HTTPException(status_code=403, detail="Invalid OTP Token")

    token = create_token(data)
    CONFIG.info("Valid OTP - token issued")

    return AuthToken(token=token)