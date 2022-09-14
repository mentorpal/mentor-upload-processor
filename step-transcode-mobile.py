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
from media_tools import (
    get_video_file_type,
    video_encode_for_mobile,
    ffmpeg_barebones_transcode,
)
from module.api import (
    UpdateTaskStatusRequest,
    AnswerUpdateRequest,
    upload_task_status_update,
    upload_answer_and_task_status_update,
)
from module.utils import (
    s3_bucket,
    load_sentry,
    fetch_from_graphql,
)
from module.constants import Supported_Video_Type, MP4

load_sentry()
log = logger.get_logger("answer-transcode-mobile-handler")
s3 = boto3.client("s3")


def transcode_mobile(video_file, video_file_type: Supported_Video_Type, s3_path):
    work_dir = os.path.dirname(video_file)
    target_file = f"mobile.{video_file_type.extension}"
    target_file_path = os.path.join(work_dir, target_file)

    video_encode_for_mobile(video_file, target_file_path, video_file_type.mime)

    log.info("uploading %s to %s/%s", target_file_path, s3_bucket, s3_path)
    s3.upload_file(
        target_file_path,
        s3_bucket,
        f"{s3_path}/{target_file}",
        ExtraArgs={"ContentType": video_file_type.mime},
    )

    # webm are also transcoded to mp4 for browsers that do not support webm
    if video_file_type.mime == "video/webm":
        mp4_target_file = "mobile.mp4"
        mp4_target_file_path = os.path.join(work_dir, mp4_target_file)
        ffmpeg_barebones_transcode(target_file_path, mp4_target_file_path)
        log.info("uploading %s to %s/%s", mp4_target_file_path, s3_bucket, s3_path)
        s3.upload_file(
            mp4_target_file_path,
            s3_bucket,
            f"{s3_path}/{mp4_target_file}",
            ExtraArgs={"ContentType": "video/mp4"},
        )


def process_task(request):
    log.info("video to process %s", request["video"])
    stored_task = fetch_from_graphql(
        request["mentor"], request["question"], "transcodeMobileTask"
    )
    if not stored_task:
        log.warn("task not found, skipping transcode")
        return

    if stored_task["status"].startswith("CANCEL"):
        log.info("task cancelled, skipping transcription")
        return

    with tempfile.TemporaryDirectory() as work_dir:
        work_file = os.path.join(work_dir, "original_video")
        s3.download_file(s3_bucket, request["video"], work_file)

        try:
            video_file_type = get_video_file_type(work_file)
        except Exception as e:
            log.debug(e)
            log.debug("unknown file mime type, will attempt to transcode to mp4")
            video_file_type = MP4

        s3_path = os.path.dirname(request["video"])  # same 'folder' as original file
        log.info("%s downloaded to %s", request["video"], work_dir)

        upload_task_status_update(
            UpdateTaskStatusRequest(
                mentor=request["mentor"],
                question=request["question"],
                transcode_mobile_task={"status": "IN_PROGRESS"},
            )
        )

        transcode_mobile(work_file, video_file_type, s3_path)

        mobile_media = {
            "type": "video",
            "tag": "mobile",
            "url": f"{s3_path}/mobile.{video_file_type.extension}",
            "transparentVideoUrl": f"{s3_path}/mobile.MP4"
            if video_file_type.mime == "video/mp4"
            else "",  # webms are also created if the mime type is webm
        }

        upload_answer_and_task_status_update(
            AnswerUpdateRequest(
                mentor=request["mentor"],
                question=request["question"],
                mobile_media=mobile_media,
            ),
            UpdateTaskStatusRequest(
                mentor=request["mentor"],
                question=request["question"],
                transcode_mobile_task={"status": "DONE"},
                mobile_media=mobile_media,
            ),
        )


def handler(event, context):
    log.info(json.dumps(event))
    request = event["request"]

    task = request["transcodeMobileTask"] if "transcodeMobileTask" in request else None
    if not task:
        log.warning("no transcoding-mobile task requested")
        return

    process_task(request)
