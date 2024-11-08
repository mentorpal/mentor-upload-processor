#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
import base64
import boto3
import os
from cgi import parse_header, FieldStorage
from io import BytesIO
from urllib.parse import urljoin
from module.api import (
    MentorVttUpdateRequest,
    mentor_vtt_update,
    user_can_edit_mentor,
)
from module.logger import get_logger
from module.utils import (
    create_json_response,
    get_text_from_file,
    s3_bucket,
    load_sentry,
    require_env,
    get_auth_headers,
)
from module.vtt_utils import vtt_file_validation


load_sentry()
log = get_logger("vtt-upload")
aws_region = require_env("REGION")
s3_client = boto3.client("s3", region_name=aws_region)


def handler(event, context):
    log.info(event)
    if "body" not in event:
        data = {
            "error": "Bad Request",
            "message": "body payload is required",
        }
        return create_json_response(401, data, event)
    content_type_casing = (
        "content-type" if ("content-type" in event["headers"]) else "Content-Type"
    )

    c_type, c_data = parse_header(event["headers"][content_type_casing])
    if c_type != "multipart/form-data":
        data = {
            "error": "Bad Request",
            "message": "only multipart uploads are accepted",
        }
        return create_json_response(401, data, event)

    if event["isBase64Encoded"]:
        body = base64.b64decode(event["body"])
    else:
        body = event["body"]
    environ = {"REQUEST_METHOD": "POST"}
    headers = {
        "content-type": event["headers"][content_type_casing],
    }

    form_data = FieldStorage(fp=BytesIO(body), environ=environ, headers=headers)
    print(form_data, flush=True)
    if "mentor" not in form_data:
        data = {
            "error": "Bad Request",
            "message": "missing required form params (mentor)",
        }
        return create_json_response(401, data, event)
    if "question" not in form_data:
        data = {
            "error": "Bad Request",
            "message": "missing required form params (question)",
        }
        return create_json_response(401, data, event)
    if "vtt_file" not in form_data:
        data = {
            "error": "Bad Request",
            "message": "missing required form params (vtt_file)",
        }
        return create_json_response(401, data, event)
    log.debug("form keys: %s", form_data.keys())

    # vtt validation
    try:
        vtt_file = form_data["vtt_file"]
        local_vtt_file_path = "/tmp/en.vtt"
        os.makedirs(os.path.dirname(local_vtt_file_path), exist_ok=True)
        with open(local_vtt_file_path, "wb") as file:
            file.write(vtt_file.value)
        vtt_file_validation(local_vtt_file_path)
    except Exception as e:
        log.error("Failed to validate vtt file")
        data = {
            "error": "VTT File Validation Failed",
            "message": str(e),
        }
        return create_json_response(401, data, event)

    auth_headers = get_auth_headers(event)

    mentor = form_data["mentor"].value
    question_id = form_data["question"].value
    auth_headers = get_auth_headers(event)
    if not user_can_edit_mentor(mentor, auth_headers):
        data = {
            "error": "not authorized",
            "message": "not authorized",
        }
        return create_json_response(401, data, event)

    s3_vtt_path = f"videos/{mentor}/{question_id}/en.vtt"

    s3_client.upload_fileobj(
        form_data["vtt_file"].file,
        s3_bucket,
        s3_vtt_path,
        ExtraArgs={"ContentType": "text"},
    )

    vtt_text = get_text_from_file(local_vtt_file_path)

    mentor_vtt_update(
        MentorVttUpdateRequest(
            mentor=mentor, question=question_id, vtt_url=s3_vtt_path, vtt_text=vtt_text
        ),
        auth_headers,
    )

    static_url_base = require_env("STATIC_URL_BASE")
    data = {
        "data": {
            "vtt_path": urljoin(static_url_base, s3_vtt_path),
            "vtt_text": vtt_text,
        }
    }

    return create_json_response(200, data, event)


# # for local debugging:
# if __name__ == "__main__":
#     with open("__events__/vbg-event.json") as f:
#         event = json.loads(f.read())
#         handler(event, {})
