import requests
import json
from .util import get_auth_headers, api_endpoint
from PIL import Image as PILImage
from io import BytesIO
from os import urandom  # 3.9 introduced random.randbytes
from urllib3 import encode_multipart_formdata


def test_successful_upload():
    test_mentor = "6196af5e068d43dc686194f8"  # milan, todo: create a test mentor
    # generate a random 100x100px png:
    tobytes = urandom(100) + b" \xd2\xb7\xe1"
    img = PILImage.frombytes("L", (10, 10), tobytes)
    img_data = BytesIO()
    img.save(img_data, "PNG", subsampling=0, quality=100)
    fields = {
        "body": json.dumps({"mentor": test_mentor}),
        "thumbnail": ("random.png", img_data.getvalue(), "image/png"),
    }
    body, content_type = encode_multipart_formdata(fields)
    headers = get_auth_headers(test_mentor)
    headers["Content-Type"] = content_type

    response = requests.post(
        f"{api_endpoint}/thumbnail",
        headers=headers,
        data=body,
    )

    print(response.status_code, response.text)
    assert response.status_code == 200
    assert "thumbnails/6196af5e068d43dc686194f8" in response.text
