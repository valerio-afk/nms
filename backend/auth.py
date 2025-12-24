from backend.config import ConfigMixin
import pyotp


class AuthMixin(ConfigMixin):
    @property
    def is_otp_configured(this):
        return this._cfg['access'].get("otp_secret",None) is not None

    def set_otp_secret(this,secret):
        this._cfg['access']['otp_secret'] = secret
        this.flush_config()

    def verify_otp(this,otp):
        secret = this._cfg['access'].get('otp_secret',None)

        if (secret is not None):
            totp = pyotp.TOTP(secret)
            return totp.verify(otp)

        return False