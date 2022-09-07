import requests
from .util import get_auth_headers, api_endpoint


def test_upload_url():
    response = requests.get(f"{api_endpoint}/upload/url", headers=get_auth_headers())
    print(response.status_code, response.text) # for debugging if test fails
    assert response.status_code == 200
    assert "AWSAccessKeyId" in response.text
    assert "url" in response.text
