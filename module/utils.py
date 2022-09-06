# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
#

import json
import os
from os import _Environ, environ
from typing import Any, Dict, Union
from module.logger import get_logger
from module.api import fetch_task


log = get_logger()
FFMPEG_EXECUTABLE = os.environ.get("FFMPEG_EXECUTABLE", "/opt/ffmpeg/ffmpeg")


def require_env(n: str) -> str:
    env_val = environ.get(n, "")
    if not env_val:
        raise EnvironmentError(f"missing required env var {n}")
    return env_val


s3_bucket = require_env("S3_STATIC_ARN").split(":")[-1]
log.info("using s3 bucket %s", s3_bucket)

aws_region = require_env("REGION")


# s3_key format: */*/*.extension
def get_file_extension_from_s3_key(s3_key: str) -> str:
    video_file_name = s3_key.split("/")[-1]
    video_file_extension = video_file_name.split(".")[-1]
    return video_file_extension


def load_sentry():
    if environ.get("IS_SENTRY_ENABLED", "") == "true":
        log.info("SENTRY enabled, calling init")
        import sentry_sdk  # NOQA E402
        from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration  # NOQA E402

        sentry_sdk.init(
            dsn=environ.get("SENTRY_DSN_MENTOR_CLASSIFIER"),
            # include project so issues can be filtered in sentry:
            environment=environ.get("PYTHON_ENV"),
            integrations=[AwsLambdaIntegration(timeout_warning=True)],
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            traces_sample_rate=0.20,
            debug=environ.get("SENTRY_DEBUG_UPLOADER", "") == "true",
        )


def is_authorized(mentor, token):
    return (
        token["role"] == "CONTENT_MANAGER"
        or token["role"] == "ADMIN"
        or mentor in token["mentorIds"]
    )


def create_json_response(status, data, event, headers={}):
    body = {"data": data}
    append_cors_headers(headers, event)
    append_secure_headers(headers)
    response = {"statusCode": status, "body": json.dumps(body), "headers": headers}
    return response


def append_secure_headers(headers):
    secure = {
        "content-security-policy": "upgrade-insecure-requests;",
        "referrer-policy": "no-referrer-when-downgrade",
        "strict-transport-security": "max-age=31536000",
        "x-content-type-options": "nosniff",
        "x-frame-options": "SAMEORIGIN",
        "x-xss-protection": "1; mode=block",
    }
    for h in secure:
        headers[h] = secure[h]


def append_cors_headers(headers, event):
    origin = environ.get("CORS_ORIGIN", "*")
    # TODO specify allowed list of origins and if event["headers"]["origin"] is one of them then allow it
    # if "origin" in event["headers"] and getenv.array('CORS_ORIGIN').includes(event["headers"]["origin"]):
    #     origin = event["headers"]["origin"]
    headers["Access-Control-Allow-Origin"] = origin
    headers["Access-Control-Allow-Origin"] = "*"
    headers["Access-Control-Allow-Headers"] = "GET,PUT,POST,DELETE,OPTIONS"
    headers[
        "Access-Control-Allow-Methods"
    ] = "Authorization,Origin,Accept,Accept-Language,Content-Language,Content-Type"


def props_to_bool(
    name: str, props: Union[Dict[str, Any], _Environ], dft: bool = False
) -> bool:
    if not (props and name in props):
        return dft
    v = props[name]
    return str(v).lower() in ["1", "t", "true"]


def format_secs(secs: Union[float, int, str]) -> str:
    return f"{float(str(secs)):.3f}"


def fetch_from_graphql(mentor, question, task_name):
    upload_task = fetch_task(mentor, question)
    if not upload_task:
        # this can happen if any task status is failed and client deletes the task
        return None
    stored_task = upload_task[task_name] if task_name in upload_task else None
    if stored_task is None:
        log.error("task does not exist in upload task %s", upload_task)
        raise Exception("task does not exist in upload task %s", upload_task)
    return stored_task
