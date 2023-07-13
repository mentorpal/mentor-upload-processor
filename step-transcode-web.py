#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#

import boto3
import tempfile
import os
from module.logger import get_logger

from module.constants import Supported_Video_Type, MP4, WEBM_VP9
from media_tools import (
    get_file_mime,
    get_video_metadata,
    video_encode_for_web,
    ffmpeg_barebones_transcode,
    get_video_encoding_type,
)
from module.api import (
    UpdateTaskStatusRequest,
    AnswerUpdateRequest,
    upload_task_status_update,
    upload_answer_and_task_status_update,
)
from module.utils import s3_bucket, load_sentry, fetch_from_graphql

load_sentry()
log = get_logger("answer-transcode-web-handler")
s3 = boto3.client("s3")


def transcode_web(
    video_file,
    video_file_type: Supported_Video_Type,
    s3_path,
    maintain_original_aspect_ratio,
):
    work_dir = os.path.dirname(video_file)
    target_file = f"web.{video_file_type.extension}"
    target_file_path = os.path.join(work_dir, target_file)

    video_encode_for_web(
        video_file,
        target_file_path,
        video_file_type.mime,
        maintain_original_aspect_ratio=maintain_original_aspect_ratio,
    )

    log.info("uploading %s to %s/%s", target_file_path, s3_bucket, s3_path)
    s3.upload_file(
        target_file_path,
        s3_bucket,
        f"{s3_path}/{target_file}",
        ExtraArgs={"ContentType": video_file_type.mime},
    )

    # webm are also transcoded to mp4 for browsers that do not support webm
    if video_file_type.mime == "video/webm":
        mp4_target_file = "web.mp4"
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
    auth_headers = request["authHeaders"]
    maintain_original_aspect_ratio = request["maintain_original_aspect_ratio"]
    log.info("video to process %s", request["video"])
    stored_task = fetch_from_graphql(
        request["mentor"], request["question"], "transcodeWebTask", auth_headers
    )
    if not stored_task:
        log.warning("task not found, skipping transcode")
        return

    if stored_task["status"].startswith("CANCEL"):
        log.info("task cancelled, skipping transcription")
        return

    with tempfile.TemporaryDirectory() as work_dir:
        work_file = os.path.join(work_dir, "original_video")
        s3.download_file(s3_bucket, request["video"], work_file)

        is_vbg_video = request["isVbgVideo"] if "isVbgVideo" in request else False
        if is_vbg_video:
            try:

                file_mime_type = get_file_mime(work_file)
                file_encoding = get_video_encoding_type(work_file)
                if file_mime_type == "video/webm" and file_encoding == "vp9":
                    desired_video_file_type = WEBM_VP9
                else:
                    desired_video_file_type = MP4
            except Exception as e:
                log.info(
                    f"Failed to determine mime and encoding type for {work_file}, defaulting to mp4"
                )
                log.info(e)
                desired_video_file_type = MP4
        else:
            desired_video_file_type = MP4

        s3_path = os.path.dirname(request["video"])
        log.info("%s downloaded to %s", request["video"], work_dir)
        upload_task_status_update(
            UpdateTaskStatusRequest(
                mentor=request["mentor"],
                question=request["question"],
                transcode_web_task={"status": "IN_PROGRESS"},
            ),
            auth_headers,
        )

        transcode_web(
            work_file, desired_video_file_type, s3_path, maintain_original_aspect_ratio
        )

        video_metadata_string, duration, video_hash = get_video_metadata(work_file)
        web_media = {
            "duration": duration,
            "hash": video_hash,
            "stringMetadata": video_metadata_string,
            "type": "video",
            "tag": "web",
            "url": f"{s3_path}/web.mp4",  # mp4's are always created
            "transparentVideoUrl": f"{s3_path}/web.webm"
            if desired_video_file_type.mime == "video/webm"
            else "",  # webms are also created if the mime type is webm
        }

        upload_answer_and_task_status_update(
            AnswerUpdateRequest(
                mentor=request["mentor"],
                question=request["question"],
                web_media=web_media,
            ),
            UpdateTaskStatusRequest(
                mentor=request["mentor"],
                question=request["question"],
                transcode_web_task={"status": "DONE"},
                web_media=web_media,
            ),
            auth_headers,
        )


def handler(event, context):
    log.info(event)
    request = event["request"]

    task = request["transcodeWebTask"] if "transcodeWebTask" in request else None
    if not task:
        log.warning("no transcoding-web task requested")
        return

    process_task(request)
