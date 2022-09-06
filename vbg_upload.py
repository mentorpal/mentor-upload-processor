#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
import base64
import boto3
import json
from datetime import datetime
from cgi import parse_header, FieldStorage
from io import BytesIO
from urllib.parse import urljoin
from module.api import (
    MentorVbgUpdateRequest,
    mentor_vbg_update,
)
from module.logger import get_logger
from module.utils import (
    create_json_response,
    s3_bucket,
    is_authorized,
    load_sentry,
    require_env,
)


load_sentry()
log = get_logger("vbg-upload")
aws_region = require_env("REGION")
s3_client = boto3.client("s3", region_name=aws_region)


def handler(event, context):
    log.debug(json.dumps(event))
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
    if "body" not in form_data or "background_image" not in form_data:
        data = {
            "error": "Bad Request",
            "message": "missing required form params (body, background_image)",
        }
        return create_json_response(401, data, event)
    log.debug("form keys: %s", form_data.keys())
    if (
        form_data["background_image"].type != "image/png"
        and form_data["background_image"].type != "image/jpeg"
    ):
        data = {"error": "Bad Request", "message": "only png/jpg images are accepted"}
        return create_json_response(401, data, event)

    vbg_request = json.loads(form_data["body"].value)
    if "mentor" not in vbg_request:
        data = {
            "error": "Bad Request",
            "message": "mentor parameter missing",
        }
        return create_json_response(401, data, event)

    mentor = vbg_request["mentor"]
    token = json.loads(event["requestContext"]["authorizer"]["token"])
    if not is_authorized(mentor, token):
        data = {
            "error": "not authorized",
            "message": "not authorized",
        }
        return create_json_response(401, data, event)

    virtual_background_path = f"mentor/virtual_backgrounds/{mentor}/{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}/virtual_background.png"
    s3_client.upload_fileobj(
        form_data["background_image"].file,
        s3_bucket,
        virtual_background_path,
        ExtraArgs={"ContentType": "image/png"},
    )
    mentor_vbg_update(
        MentorVbgUpdateRequest(mentor=mentor, vbgPath=virtual_background_path)
    )
    static_url_base = require_env("STATIC_URL_BASE")
    data = {
        "data": {"virtualBackground": urljoin(static_url_base, virtual_background_path)}
    }

    return create_json_response(200, data, event)


# # for local debugging:
# if __name__ == "__main__":
#     with open("__events__/vbg-event.json") as f:
#         event = json.loads(f.read())
#         handler(event, {})
