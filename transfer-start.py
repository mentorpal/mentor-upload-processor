#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
import base64
import boto3
import json
import uuid
import gzip
from datetime import datetime
from os import environ
from module.logger import get_logger
from module.transfer_mentor_schema import transfer_mentor_json_schema
from jsonschema import validate, ValidationError
from module.api import import_task_create_gql, ImportTaskGQLRequest
from module.utils import create_json_response, is_authorized, load_sentry, require_env


load_sentry()
log = get_logger("transfer-start")
ttl_sec = environ.get("TTL_SEC", (60 * 60 * 24) * 180)  # 180 days
aws_region = require_env("REGION")
JOBS_TABLE_NAME = require_env("JOBS_TABLE_NAME")
log.info(f"using table {JOBS_TABLE_NAME}")
dynamodb = boto3.resource("dynamodb", region_name=aws_region)
job_table = dynamodb.Table(JOBS_TABLE_NAME)


def handler(event, context):
    log.info(event)
    if "body" not in event:
        data = {
            "error": "Bad Request",
            "message": "body payload is required",
        }
        return create_json_response(401, data, event)

    if event["isBase64Encoded"]:
        body = base64.b64decode(event["body"])
    else:
        body = event["body"]

    transfer_request = json.loads(body)
    try:
        validate(instance=transfer_request, schema=transfer_mentor_json_schema)
    except ValidationError as err:
        log.warn(err)
        data = {
            "error": "Bad Request",
            "message": f"invalid payload: {err}",
        }
        return create_json_response(401, data, event)

    mentor = transfer_request["mentor"]
    token = json.loads(event["requestContext"]["authorizer"]["token"])
    if not is_authorized(mentor, token):
        data = {
            "error": "not authorized",
            "message": "not authorized",
        }
        return create_json_response(401, data, event)

    # this tends to be large so to avoid 400kb max item size:
    compressed_body = gzip.compress(bytes(body, "utf-8"))

    graphql_update = {"status": "QUEUED"}
    s3_video_migration = {"status": "QUEUED"}
    import_task_create_gql(
        ImportTaskGQLRequest(mentor, graphql_update, s3_video_migration)
    )
    job_id = str(uuid.uuid4())
    train_job = {
        "id": job_id,
        "mentor": mentor,
        "status": "QUEUED",
        "payload": boto3.dynamodb.types.Binary(compressed_body),
        "created": datetime.now().isoformat(),
        # https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/time-to-live-ttl-before-you-start.html#time-to-live-ttl-before-you-start-formatting
        "ttl": int(datetime.now().timestamp()) + ttl_sec,
    }
    job_table.put_item(Item=train_job)
    data = {
        "id": job_id,
        "mentor": mentor,
        "status": "QUEUED",
        "statusUrl": f"/transfer/status/{job_id}",
    }

    return create_json_response(200, data, event)


# # for local debugging:
# if __name__ == "__main__":
#     with open("__events__/transfer-start-event.json.dist") as f:
#         event = json.loads(f.read())
#         handler(event, {})
