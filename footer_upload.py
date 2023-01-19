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
    OrgFooterUpdateRequest,
    org_footer_update,
)
from module.logger import get_logger
from module.utils import (
    create_json_response,
    s3_bucket,
    is_authorized,
    is_authorized_for_org,
    load_sentry,
    require_env,
    get_auth_headers,
)


load_sentry()
log = get_logger("footer-upload")
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
    if "body" not in form_data or "image" not in form_data:
        data = {
            "error": "Bad Request",
            "message": "missing required form params (body, image)",
        }
        return create_json_response(401, data, event)
    log.debug("form keys: %s", form_data.keys())
    if (
        form_data["image"].type != "image/png"
        and form_data["image"].type != "image/jpeg"
    ):
        data = {"error": "Bad Request", "message": "only png/jpg images are accepted"}
        return create_json_response(401, data, event)
    
    auth_headers = get_auth_headers(event)
    img_request = json.loads(form_data["body"].value)
    org = img_request["org"]
    idx = img_request["idx"]
    token = json.loads(event["requestContext"]["authorizer"]["token"])
    if org:
        if not is_authorized_for_org(org, token):
            data = {
                "error": "not authorized",
                "message": "not authorized",
            }
            return create_json_response(401, data, event)
    else if not is_authorized("", token):
        data = {
            "error": "not authorized",
            "message": "not authorized",
        }
        return create_json_response(401, data, event)

    image_path = ""
    if org:
        image_path = f"images/{org["_id"]}/{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}/footer.png"
    else:
        image_path = f"images/{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}/footer.png"
    s3_client.upload_fileobj(
        form_data["image"].file,
        s3_bucket,
        image_path,
        ExtraArgs={"ContentType": "image/png"},
    )
    static_url_base = require_env("STATIC_URL_BASE")
    image_url = urljoin(static_url_base, image_path)
    if org:
        org_footer_update(
            OrgFooterUpdateRequest(orgId=org["_id"], imgPath=image_url, imgIdx=idx),
            auth_headers,
        )
    else:
        org_footer_update(
            OrgFooterUpdateRequest(imgPath=image_url, imgIdx=idx),
            auth_headers,
        )
    data = {
        "data": {"image": image_url}
    }

    return create_json_response(200, data, event)
