import requests
from .util import headers, api_endpoint

def test_upload_url():
    response = requests.get(f"{api_endpoint}/upload/url", headers=headers)
    print(headers, response.status_code, response.text)
    assert response.status_code == 200 
    assert "AWSAccessKeyId" in response.text
    assert "url" in response.text
