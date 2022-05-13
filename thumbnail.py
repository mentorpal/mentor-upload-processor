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
from os import environ
from cgi import parse_header, FieldStorage
from io import BytesIO
from urllib.parse import urljoin
from module.api import (
    MentorThumbnailUpdateRequest,
    mentor_thumbnail_update,
)

from module.logger import get_logger
from module.utils import create_json_response, s3_bucket, is_authorized, load_sentry


load_sentry()
log = get_logger("upload-answer")
aws_region = environ.get("REGION", "us-east-1")
s3_client = boto3.client("s3", region_name=aws_region)


thumbnail_upload_json_schema = {
    "type": "object",
    "properties": {
        "mentor": {"type": "string", "maxLength": 60, "minLength": 5},
    },
    "required": ["mentor"],
    "additionalProperties": False,
}


# TODO: probably want to force the size and quality of this image
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
        # "content-length": event['headers']["Content-Length"], # curl didnt send it!?
    }

    form_data = FieldStorage(fp=BytesIO(body), environ=environ, headers=headers)
    if "body" not in form_data or "thumbnail" not in form_data:
        data = {
            "error": "Bad Request",
            "message": "missing required form params (body, thumbnail)",
        }
        return create_json_response(401, data, event)
    log.debug("form keys: %s", form_data.keys())
    if form_data["thumbnail"].type != "image/png":
        data = {"error": "Bad Request", "message": "only png images are accepted"}
        return create_json_response(401, data, event)

    thumbnail_request = json.loads(form_data["body"].value)
    if "mentor" not in thumbnail_request:
        data = {
            "error": "Bad Request",
            "message": "mentor parameter missing",
        }
        return create_json_response(401, data, event)

    mentor = thumbnail_request["mentor"]
    token = json.loads(event["requestContext"]["authorizer"]["token"])
    if not is_authorized(mentor, token):
        data = {
            "error": "not authorized",
            "message": "not authorized",
        }
        return create_json_response(401, data, event)

    thumbnail_path = f"mentor/thumbnails/{mentor}/{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}/thumbnail.png"
    s3_client.upload_fileobj(
        form_data["thumbnail"].file,
        s3_bucket,
        thumbnail_path,
        ExtraArgs={"ContentType": "image/png"},
    )
    mentor_thumbnail_update(
        MentorThumbnailUpdateRequest(mentor=mentor, thumbnail=thumbnail_path)
    )
    static_url_base = environ.get("STATIC_URL_BASE", "")
    data = {"data": {"thumbnail": urljoin(static_url_base, thumbnail_path)}}

    return create_json_response(200, data, event)


# # for local debugging:
# if __name__ == "__main__":
#     with open("__events__/thumbnail-event.json") as f:
#         event = json.loads(f.read())
#         handler(event, {})
