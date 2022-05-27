#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#

import boto3
import json
import uuid
from os import environ
from module.logger import get_logger
from module.utils import create_json_response, load_sentry, require_env


load_sentry()
log = get_logger("upload-url")
upload_bucket = require_env("SIGNED_UPLOAD_BUCKET")
aws_region = environ.get("REGION", "us-east-1")
s3_client = boto3.client("s3", region_name=aws_region)


def handler(event, context):
    log.info("creating signed url")
    token = json.loads(event["requestContext"]["authorizer"]["token"])
    id = uuid.uuid4()
    object_name = f"{token['id']}/{id}"
    #  https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-HTTPPOSTConstructPolicy.html
    signedUrl = s3_client.generate_presigned_post(
        upload_bucket,
        object_name,
        Fields={"key": object_name},
        Conditions=[
            ["content-length-range", 0, 52_428_800],  # 50MB
            # ["starts-with", "$Content-Type", "video/"],
        ],
        ExpiresIn=3600,
    )

    data = {"url": signedUrl["url"], "fields": signedUrl["fields"]}
    return create_json_response(200, data, event)


# # for local debugging:
# if __name__ == "__main__":
#     event = {
#         "requestContext": {
#            "authorizer": {
#              "token": "{\"id\": \"6196af5e068d43dc686194ed\"}"
#            }
#         }
#     }
#     response = handler(event, {})
#     print(json.dumps(response))
