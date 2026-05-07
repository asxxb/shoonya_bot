

import logging
import pyotp
from NorenRestApiPy.NorenApi import NorenApi

logging.basicConfig(level=logging.DEBUG)

class ShoonyaApiPy(NorenApi):
    def __init__(self):
        super().__init__(
            host='https://api.shoonya.com/NorenWClientAPI',
            websocket='wss://api.shoonya.com/NorenWSTP'
        )

api = ShoonyaApiPy()

USER = 'FN210590'
PASSWORD = 'Aseeb@123'
VENDOR_CODE = 'FN210590_U'
API_SECRET = '2943b6073f6944daafe0e8c7d0867451'
IMEI = 'abc1234'
TOTP_SECRET = '356I6SB4PRHSI53UX27CE24NY27RZT25'

factor2 = pyotp.TOTP(TOTP_SECRET).now()

print("Generated OTP:", factor2)

ret = api.login(
    userid=USER,
    password=PASSWORD,
    twoFA=factor2,
    vendor_code=VENDOR_CODE,
    api_secret=API_SECRET,
    imei=IMEI
)



print("Login Response:")
print(ret)

if ret and ret.get("stat") == "Ok":

    print("\n✅ LOGIN SUCCESS")

   
else:
    print("\n❌ LOGIN FAILED")