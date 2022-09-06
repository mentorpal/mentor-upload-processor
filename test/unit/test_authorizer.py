import pytest
from authorizer import handler, extract_token_from_header
import jwt


def test_extract_fails_for_unrecognized_token():
    with pytest.raises(Exception):
        extract_token_from_header(
            {
                "type": "UNKNOWN",
            }
        )


def test_extract_fails_for_missing_token():
    with pytest.raises(Exception):
        extract_token_from_header(
            {
                "type": "TOKEN",
                "authorizationToken": "not bearer token",
            }
        )


def test_extract_fails_for_invalid_signature():
    with pytest.raises(Exception):
        extract_token_from_header(
            {
                "type": "TOKEN",
                "authorizationToken": "Bearer invalid jwt",
            }
        )


def test_extract_invalid_token_schema():
    token = {"id": "123", "role": "ADMIN", "mentorIds": ["6"]}
    encoded = jwt.encode(token, "secret", algorithm="HS256")
    with pytest.raises(Exception):
        extract_token_from_header(
            {
                "type": "TOKEN",
                "authorizationToken": f"Bearer {encoded}",
            }
        )


def test_extract_valid():
    token = {"id": "12345", "role": "ADMIN", "mentorIds": ["12345"]}
    encoded = jwt.encode(token, "secret", algorithm="HS256")
    payload = extract_token_from_header(
        {
            "type": "TOKEN",
            "authorizationToken": f"Bearer {encoded}",
        }
    )
    assert payload["id"] == "12345"


def test_handler_deny():
    token = {"id": "1", "role": "ADMIN", "mentorIds": ["12345"]}
    encoded = jwt.encode(token, "secret", algorithm="HS256")
    policy = handler(
        {
            "type": "TOKEN",
            "methodArn": "arn:aws:execute-api:us-east-1:100000000655:1111111111/dev/POST/answer/upload",
            "authorizationToken": f"Bearer {encoded}",
        },
        None,
    )
    policy["policyDocument"]["Statement"][0]["Effect"] == "Deny"


def test_handler_allow():
    token = {"id": "12345", "role": "ADMIN", "mentorIds": ["12345"]}
    encoded = jwt.encode(token, "secret", algorithm="HS256")
    policy = handler(
        {
            "type": "TOKEN",
            "methodArn": "arn:aws:execute-api:us-east-1:100000000655:1111111111/dev/POST/answer/upload",
            "authorizationToken": f"Bearer {encoded}",
        },
        None,
    )
    policy["policyDocument"]["Statement"][0]["Effect"] == "Allow"
