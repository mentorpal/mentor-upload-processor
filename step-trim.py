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
from media_tools import get_file_mime, video_trim

from module.utils import (
    s3_bucket,
    load_sentry,
    require_env,
    fetch_from_graphql,
)
from module.constants import Supported_Video_Type, supported_video_types
from module.api import (
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


def get_original_video_url(
    mentor: str, question: str, video_file_type: Supported_Video_Type
) -> str:
    base_url = os.environ.get("STATIC_URL_BASE", "")
    return f"{base_url}/videos/{mentor}/{question}/original.{video_file_type.extension}"


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
        work_file = os.path.join(work_dir, "original_video")  # don't assume file type
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

        uploaded_video_mime_type = get_file_mime(work_file)
        log.info(f"video mime type: {uploaded_video_mime_type}")
        try:
            video_file_type = next(
                video_type
                for video_type in supported_video_types
                if video_type.mime == uploaded_video_mime_type
            )
        except Exception:
            raise Exception(f"Unsupported video mime type: {uploaded_video_mime_type}")

        log.info("trimming file %s", work_file)
        trim_file = f"{work_file}-trim.{video_file_type.extension}"
        video_trim(
            work_file,
            trim_file,
            request["trim"]["start"],
            request["trim"]["end"],
        )
        log.info("trim completed")
        s3_path = f"videos/{request['mentor']}/{request['question']}"
        s3_client.upload_file(
            trim_file,
            s3_bucket,
            f"{s3_path}/original.{video_file_type.extension}",
            ExtraArgs={"ContentType": video_file_type.mime},
        )
        log.info("trimmed video uploaded")

        upload_task_status_update(
            UpdateTaskStatusRequest(
                mentor=request["mentor"],
                question=request["question"],
                trim_upload_task={"status": "DONE"},
            )
        )


def handler(event, context):
    log.info(json.dumps(event))
    request = event["request"]

    task = request["trimUploadTask"] if "trimUploadTask" in request else None
    if not task:
        log.warning("no trim task requested")
        return

    process_task(request)


# # for local debugging:
# if __name__ == "__main__":
#     with open("__events__/step-function-event.json.dist") as f:
#         event = json.loads(f.read())
#         handler(event, {})
