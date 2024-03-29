import jwt
import datetime
from module.utils import require_env

jwt_secret = require_env("JWT_SECRET")
api_endpoint = require_env("UPLOAD_ENDPOINT")


def get_auth_headers(
    id="6109d2a86e6fa01e5bf3219f", mentorIds=["6109d2a86e6fa01e5bf3219f"]
):
    exp = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(hours=1)
    token = {
        "id": id,
        "role": "ADMIN",
        "mentorIds": mentorIds,
        "iat": datetime.datetime.now(tz=datetime.timezone.utc),
        "exp": exp,
        "expirationDate": exp.isoformat(),
    }
    encoded = jwt.encode(token, jwt_secret, algorithm="HS256")

    headers = {
        "Authorization": f"Bearer {encoded}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
    }
    return headers
