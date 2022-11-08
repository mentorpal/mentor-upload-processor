#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
import json
import uuid
import boto3
import base64
import tempfile
import os

from module.constants import Supported_Video_Type, supported_video_types, MP4
from media_tools import assert_video_duration, get_video_file_type
from module.utils import (
    create_json_response,
    s3_bucket,
    is_authorized,
    load_sentry,
    require_env,
    get_auth_headers,
)
from module.api import (
    is_upload_in_progress,
    FetchUploadTaskReq,
    upload_answer_and_task_update,
    AnswerUpdateRequest,
    UploadTaskRequest,
    upload_answer_update,
)
from module.logger import get_logger


load_sentry()
log = get_logger("upload-answer")
aws_region = require_env("REGION")
s3_client = boto3.client("s3", region_name=aws_region)
sns = boto3.client("sns", region_name=aws_region)
upload_bucket = require_env("SIGNED_UPLOAD_BUCKET")
sqs_client = boto3.client("sqs", region_name=aws_region)
sfn_client = boto3.client("stepfunctions", region_name=aws_region)
step_fn_arn = require_env("ANSWER_UPLOAD_STEP_FUNCTION_ARN")


def create_task_list(trim, has_edited_transcript):
    transcode_web_task = {
        "task_name": "transcoding-web",
        "task_id": str(uuid.uuid4()),
        "status": "QUEUED",
    }
    transcode_mobile_task = {
        "task_name": "transcoding-mobile",
        "task_id": str(uuid.uuid4()),
        "status": "QUEUED",
    }
    transcribe_task = (
        {
            "task_name": "transcribing",
            "task_id": str(uuid.uuid4()),
            "status": "QUEUED",
        }
        if not has_edited_transcript
        else None
    )
    trim_upload_task = (
        {
            "task_name": "trim-upload",
            "task_id": str(uuid.uuid4()),
            "status": "QUEUED",
        }
        if trim
        else None
    )

    return transcode_web_task, transcode_mobile_task, transcribe_task, trim_upload_task


def upload_to_s3(
    file_path,
    video_file_type: Supported_Video_Type,
    s3_path,
    mentor,
    question,
    auth_headers,
):
    log.info("uploading %s to %s", file_path, s3_path)

    # to prevent data inconsistency by partial failures (new web.mp3 - old transcript...)
    # first remove old media urls from DB
    upload_answer_update(
        AnswerUpdateRequest(
            mentor,
            question,
            web_media={"type": "video", "tag": "web", "url": ""},
            mobile_media={"type": "video", "tag": "mobile", "url": ""},
            vtt_media={"type": "subtitles", "tag": "en", "url": ""},
        ),
        auth_headers,
    )
    # then remove old media in s3
    supported_extensions = list(
        map(lambda video_type: video_type.extension, supported_video_types)
    )
    all_artifacts = [
        *[f"original.{extension}" for extension in supported_extensions],
        *[f"web.{extension}" for extension in supported_extensions],
        *[f"mobile.{extension}" for extension in supported_extensions],
        "en.vtt",
    ]
    s3_client.delete_objects(
        Bucket=s3_bucket,
        Delete={"Objects": [{"Key": f"{s3_path}/{name}"} for name in all_artifacts]},
    )

    s3_client.upload_file(
        file_path,
        s3_bucket,
        f"{s3_path}/original.{video_file_type.extension}",
        ExtraArgs={"ContentType": video_file_type.mime},
    )


def get_original_video_url(
    mentor: str, question: str, video_file_type: Supported_Video_Type
) -> str:
    base_url = os.environ.get("STATIC_URL_BASE", "")
    return f"{base_url}/videos/{mentor}/{question}/original.{video_file_type.extension}"


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

    upload_request = json.loads(body)

    if "mentor" not in upload_request:
        data = {
            "error": "Bad Request",
            "message": "mentor parameter missing",
        }
        return create_json_response(401, data, event)
    if "question" not in upload_request:
        data = {
            "error": "Bad Request",
            "message": "question parameter missing",
        }
        return create_json_response(401, data, event)
    if "video" not in upload_request:
        data = {
            "error": "Bad Request",
            "message": "video s3 object parameter missing",
        }
        return create_json_response(401, data, event)
    auth_headers = get_auth_headers(event)
    mentor = upload_request["mentor"]
    question = upload_request["question"]
    video_key = upload_request["video"]
    is_vbg_video = (
        upload_request["isVbgVideo"] if "isVbgVideo" in upload_request else False
    )  # vbg videos are expected to be in format of mime type webm with vp9 encoding
    trim = upload_request.get("trim")
    has_edited_transcript = upload_request.get("hasEditedTranscript")
    token = json.loads(event["requestContext"]["authorizer"]["token"])

    if not is_authorized(mentor, token):
        data = {
            "error": "not authorized",
            "message": "not authorized",
        }
        return create_json_response(401, data, event)
    upload_in_progress = is_upload_in_progress(
        FetchUploadTaskReq(mentor, question), auth_headers
    )
    if upload_in_progress:
        data = {
            "error": "upload in progress",
            "message": "There is an upload already in progress, please wait.",
        }
        return create_json_response(401, data, event)

    with tempfile.TemporaryDirectory() as work_dir:
        file_path = os.path.join(
            work_dir, "original_video"
        )  # don't assume video file type
        s3_client.download_file(upload_bucket, video_key, file_path)
        try:
            video_file_type = get_video_file_type(file_path)
        except Exception as e:
            log.debug(e)
            log.debug("unknown file mime type, will attempt to transcode to mp4")
            video_file_type = MP4

        if not assert_video_duration(file_path, 1000):
            data = {
                "error": "Bad Request",
                "message": "No video found or too short (1sec)!",
            }
            return create_json_response(401, data, event)

        s3_path = f"videos/{mentor}/{question}"
        # this will overwrite any existing file
        upload_to_s3(
            file_path, video_file_type, s3_path, mentor, question, auth_headers
        )

    (
        transcode_web_task,
        transcode_mobile_task,
        transcribe_task,
        trim_upload_task,
    ) = create_task_list(trim, has_edited_transcript)
    task_list = [transcode_web_task, transcode_mobile_task]
    if transcribe_task is not None:
        task_list.append(transcribe_task)
    if trim_upload_task is not None:
        task_list.append(trim_upload_task)

    req = {
        "request": {
            "mentor": mentor,
            "question": question,
            "video": f"{s3_path}/original.{video_file_type.extension}",
            "isVbgVideo": is_vbg_video,
            **({"trim": trim} if trim is not None else {}),
            "transcodeWebTask": transcode_web_task,
            "transcodeMobileTask": transcode_mobile_task,
            "trimUploadTask": trim_upload_task,
            "transcribeTask": transcribe_task,
            "authHeaders": auth_headers,
        }
    }

    original_video_url = get_original_video_url(mentor, question, video_file_type)
    # we risk here overriding values, perhaps processing was already done, so status is DONE
    # but this will overwrite and revert them back to QUEUED. Can we just append?
    upload_answer_and_task_update(
        AnswerUpdateRequest(mentor=mentor, question=question, transcript=""),
        UploadTaskRequest(
            mentor=mentor,
            question=question,
            transcode_web_task=transcode_web_task,
            transcode_mobile_task=transcode_mobile_task,
            trim_upload_task=trim_upload_task,
            transcribe_task=transcribe_task,
            transcript="",
            original_media={
                "type": "video",
                "tag": "original",
                "url": original_video_url,
            },
        ),
        auth_headers,
    )

    # name must be unique for AWS account, region, and state machine for 90 days
    job_name = f"{mentor}-{question}-{transcode_web_task['task_id']}"
    sfn_job_id = sfn_client.start_execution(
        stateMachineArn=step_fn_arn,
        name=job_name[:80],  # max length is 80
        input=json.dumps(req),
        # traceHeader='string' # TODO xray
    )
    log.info("step function executed %s", sfn_job_id)

    data = {
        "taskList": task_list,
        "statusUrl": "use taskList to fetch from graphql",
    }
    return create_json_response(200, data, event)


# # for local debugging:
# if __name__ == "__main__":
#     with open("__events__/answer-upload-event.json.dist") as f:
#         event = json.loads(f.read())
#         handler(event, {})
