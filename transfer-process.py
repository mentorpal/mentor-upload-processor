#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
import json
import boto3
import os
import gzip
from base64 import b64decode
from module.utils import load_sentry, require_env
from module.logger import get_logger
from module.transfer import process_transfer_mentor
from util import s3_bucket

load_sentry()
log = get_logger("transfer-process")
JOBS_TABLE_NAME = require_env("JOBS_TABLE_NAME")
log.info(f"using table {JOBS_TABLE_NAME}")
aws_region = os.environ.get("REGION", "us-east-1")
s3_client = boto3.client("s3", region_name=aws_region)
dynamodb = boto3.resource("dynamodb", region_name=aws_region)
job_table = dynamodb.Table(JOBS_TABLE_NAME)


def handler(event, context):
    log.debug(json.dumps(event))
    records = list(
        filter(
            lambda r: r["eventName"] == "INSERT"
            and r["dynamodb"]
            and r["dynamodb"]["NewImage"],
            event["Records"],
        )
    )
    log.debug("records to process: %s", len(records))
    for record in records:
        payload = b64decode(record["dynamodb"]["NewImage"]["payload"]["B"])  # binary
        request = json.loads(gzip.decompress(payload).decode("utf-8"))
        # todo update status
        process_transfer_mentor(s3_client, s3_bucket, request)
        # todo update status


# # for local debugging:
# if __name__ == '__main__':
#     with open('__events__/transfer-process-event.json.dist') as f:
#         event = json.loads(f.read())
#         handler(event, {})
