#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
import json
import jwt
from os import environ
from jsonschema import validate, ValidationError
from module.logger import get_logger
from module.utils import load_sentry


load_sentry()
log = get_logger("authorizer")
jwt_secret = environ.get("JWT_SECRET")
jwt_payload_schema = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "maxLength": 60, "minLength": 5},
        "role": {"type": "string"},
        "mentorIds": {
            "type": "array",
            "items": {"type": "string", "maxLength": 60, "minLength": 5},
        },
    },
    "required": ["id", "role", "mentorIds"],
}


def validate_json(json_data, json_schema):
    try:
        validate(instance=json_data, schema=json_schema)
    except ValidationError as err:
        log.error(err)
        raise err


def extract_token_from_header(request):
    if request["type"] != "TOKEN" or "authorizationToken" not in request:
        raise Exception("no authentication token provided")
    bearer_token = request["authorizationToken"]
    token_authentication = bearer_token.lower().startswith("bearer")
    token_split = bearer_token.split(" ")
    if not token_authentication or len(token_split) == 1:
        log.warn(bearer_token)
        raise Exception("no authentication token provided")
    token = token_split[1]
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise Exception("access token has expired")

    validate_json(payload, jwt_payload_schema)

    return payload


def handler(event, context):
    # do not log the token for security reasons:
    log.debug(f"{event['type']}, {event['methodArn']}")
    try:
        verified = extract_token_from_header(event)
        log.debug("token valid")
        return {
            "principalId": "apigateway.amazonaws.com",
            "policyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "execute-api:Invoke",
                        "Effect": "Allow",
                        # Resource: methodArn,  # this resulted in random aws request denied:
                        # https://forums.aws.amazon.com/thread.jspa?messageID=937251&#937251
                        "Resource": "*",
                    },
                ],
            },
            "context": {
                "token": json.dumps(verified),
            },
        }
    except Exception as err:
        log.warning(err)

    return {
        "principalId": "*",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "*",
                    "Effect": "Deny",
                    "Resource": "*",
                },
            ],
        },
    }
