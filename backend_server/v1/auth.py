import jwt
import pyotp
import pytz
from datetime import datetime,timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend_server.utils.config import NMSConfig

auth = APIRouter()

class OTPVerification(BaseModel):
    purpose:str
    duration:int
    otp:str


def create_token(data:OTPVerification) -> str:
    expire = datetime.now(pytz.timezone("UTC")) + timedelta(minutes=data.duration)

    payload = {"purpose":data.purpose,"exp":expire}

    #TODO: secret must be taken from ENV
    secret_key = "test_secret_key"

    encoded_jwt = jwt.encode(payload, secret_key, algorithm="HS256")
    return encoded_jwt




@auth.get("/auth/otp/get/<prop>")
def auth_get_property(prop:str) -> dict:
    match prop:
        case "is_configured":
            return {
                "property":prop,
                "value": NMSConfig().is_otp_configured
            }
        case _:
            raise HTTPException(status_code=404, detail=f"Property {prop} not valid for auth")

@auth.get("/auth/otp/new")
def auth_new_secret() -> dict:
    config = NMSConfig()

    if (config.is_otp_configured):
        config.error("OTP is already configured")
        raise HTTPException(status_code=403, detail="You have already configured an OTP")

    secret = pyotp.random_base32()
    NMSConfig.temporary_otp_secret = secret

    config.info("New OTP secret generated")

@auth.post("/auth/otp/verify")
def auth_otp_verify(data:OTPVerification) -> dict:
    config = NMSConfig()

    if (not config.is_otp_configured):
        if (config.temporary_otp_secret is not None):
            config.save_otp_secret()
        else:
            raise HTTPException(status_code=403, detail="You have not configured the OTP secret")

    secret = config.otp_secret

    totp = pyotp.TOTP(secret)

    if not totp.verify(data.otp):
        raise HTTPException(status_code=403, detail="Invalid OTP Token")

    token = create_token(data)

    return {"token": token}