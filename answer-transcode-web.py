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
import logger
from media_tools import video_encode_for_web
from api import (
    UpdateTaskStatusRequest,
    AnswerUpdateRequest,
    upload_task_status_update,
    upload_answer_and_task_status_update,
)
from util import s3_bucket, load_sentry, fetch_from_graphql

load_sentry()
log = logger.get_logger("answer-transcode-web-handler")
s3 = boto3.client("s3")


def transcode_web(video_file, s3_path):
    work_dir = os.path.dirname(video_file)
    web_mp4 = os.path.join(work_dir, "web.mp4")

    video_encode_for_web(video_file, web_mp4)

    log.info("uploading %s to %s/%s", web_mp4, s3_bucket, s3_path)
    s3.upload_file(
        web_mp4,
        s3_bucket,
        f"{s3_path}/web.mp4",
        ExtraArgs={"ContentType": "video/mp4"},
    )


def process_task(request, task):
    log.info("video to process %s", request["video"])
    stored_task = fetch_from_graphql(
        request["mentor"], request["question"], task["task_id"]
    )
    if not stored_task:
        log.warn("task not found, skipping transcode")
        return

    if stored_task["status"].startswith("CANCEL"):
        log.info("task cancelled, skipping transcription")
        return

    with tempfile.TemporaryDirectory() as work_dir:
        work_file = os.path.join(work_dir, "original.mp4")
        s3.download_file(s3_bucket, request["video"], work_file)
        s3_path = os.path.dirname(request["video"])
        log.info("%s downloaded to %s", request["video"], work_dir)
        upload_task_status_update(
            UpdateTaskStatusRequest(
                mentor=request["mentor"],
                question=request["question"],
                task_id=task["task_id"],
                new_status="IN_PROGRESS",
            )
        )
        transcode_web(work_file, s3_path)
        media = [
            {
                "type": "video",
                "tag": "web",
                "url": f"{s3_path}/web.mp4",
            }
        ]
        upload_answer_and_task_status_update(
            AnswerUpdateRequest(
                mentor=request["mentor"],
                question=request["question"],
                media=media,
            ),
            UpdateTaskStatusRequest(
                mentor=request["mentor"],
                question=request["question"],
                task_id=task["task_id"],
                new_status="DONE",
                media=media,
            ),
        )


def handler(event, context):
    log.info(json.dumps(event))
    for record in event["Records"]:
        body = json.loads(str(record["body"]))
        request = json.loads(str(body["Message"]))["request"]
        task_list = request["task_list"]
        task = next(filter(lambda t: t["task_name"] == "transcoding-web", task_list))
        if not task:
            log.warning("no transcoding-web task requested")
            return

        try:
            process_task(request, task)
        except Exception as x:
            upload_task_status_update(
                UpdateTaskStatusRequest(
                    mentor=request["mentor"],
                    question=request["question"],
                    task_id=task["task_id"],
                    new_status="FAILED",
                )
            )
            raise x
