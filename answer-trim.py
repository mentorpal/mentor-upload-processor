#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
import json
import boto3
import tempfile
import os

from module.utils import (
    s3_bucket,
    load_sentry,
    require_env,
    video_trim,
)
from util import fetch_from_graphql

from api import (
    UpdateTaskStatusRequest,
    upload_task_status_update,
)
from module.logger import get_logger


load_sentry()
log = get_logger("upload-answer-trim")
aws_region = require_env("REGION")
s3_client = boto3.client("s3", region_name=aws_region)
sns = boto3.client("sns", region_name=aws_region)
upload_bucket = require_env("SIGNED_UPLOAD_BUCKET")
upload_arn = require_env("UPLOAD_SNS_ARN")
log.info(f"upload sns arn: {upload_arn}")


def get_original_video_url(mentor: str, question: str) -> str:
    base_url = os.environ.get("STATIC_URL_BASE", "")
    return f"{base_url}/videos/{mentor}/{question}/original.mp4"


def process_task(request):
    stored_task = fetch_from_graphql(
        request["mentor"], request["question"], "trimUploadTask"
    )
    if not stored_task:
        log.warn("task not found, skipping transcode")
        return

    if stored_task["status"].startswith("CANCEL"):
        log.info("task cancelled, skipping trim")
        return

    with tempfile.TemporaryDirectory() as work_dir:
        work_file = os.path.join(work_dir, "original.mp4")
        s3_client.download_file(s3_bucket, request["video"], work_file)
        s3_path = os.path.dirname(request["video"])
        log.info("%s downloaded to %s", request["video"], work_dir)
        upload_task_status_update(
            UpdateTaskStatusRequest(
                mentor=request["mentor"],
                question=request["question"],
                trim_upload_task={"status": "IN_PROGRESS"},
            )
        )

        log.info("trimming file %s", work_file)
        trim_file = f"{work_file}-trim.mp4"
        video_trim(
            work_file,
            trim_file,
            request["trimUploadTask"]["start"],
            request["trimUploadTask"]["end"],
        )
        log.info("trim completed")
        s3_path = f"videos/{request['mentor']}/{request['question']}"
        s3_client.upload_file(
            trim_file,
            s3_bucket,
            f"{s3_path}/original.mp4",
            ExtraArgs={"ContentType": "video/mp4"},
        )
        log.info("trimmed video uploaded")

        log.info("sending transc* job request %s", request)
        # todo test failure if we need to check sns_msg.ResponseMetadata.HTTPStatusCode != 200
        sns_msg = sns.publish(
            TopicArn=upload_arn, Message=json.dumps({"request": request})
        )
        log.info("sns message published %s", json.dumps(sns_msg))

        upload_task_status_update(
            UpdateTaskStatusRequest(
                mentor=request["mentor"],
                question=request["question"],
                trim_upload_task={"status": "DONE"},
            )
        )


def handler(event, context):
    log.info(json.dumps(event))
    for record in event["Records"]:
        body = json.loads(str(record["body"]))
        request = body["request"]
        task = request["trimUploadTask"] if "trimUploadTask" in request else None
        if not task:
            log.warning("no trim task requested")
            return

        try:
            process_task(request)
        except Exception as x:
            log.error(x)
            upload_task_status_update(
                UpdateTaskStatusRequest(
                    mentor=request["mentor"],
                    question=request["question"],
                    trim_upload_task={"status": "FAILED"},
                )
            )
            raise x


# # for local debugging:
if __name__ == "__main__":
    with open("__events__/answer-trim-upload-event.json.dist") as f:
        event = json.loads(f.read())
        handler(event, {})
