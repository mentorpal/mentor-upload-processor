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

from media_tools import assert_video_duration
from module.utils import (
    create_json_response,
    s3_bucket,
    is_authorized,
    load_sentry,
    require_env,
    video_trim,
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
aws_region = os.environ.get("REGION", "us-east-1")
s3_client = boto3.client("s3", region_name=aws_region)
sns = boto3.client("sns", region_name=aws_region)
upload_bucket = require_env("SIGNED_UPLOAD_BUCKET")
upload_arn = require_env("UPLOAD_SNS_ARN")
log.info(f"upload sns arn: {upload_arn}")


def submit_job(req):
    log.info("publishing job request %s", req)
    # todo test failure if we need to check sns_msg.ResponseMetadata.HTTPStatusCode != 200
    sns_msg = sns.publish(TopicArn=upload_arn, Message=json.dumps(req))
    log.info("sns message published %s", json.dumps(sns_msg))


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
            "status": "DONE",
        }
        if trim
        else None
    )

    return transcode_web_task, transcode_mobile_task, transcribe_task, trim_upload_task


def upload_to_s3(file_path, s3_path, mentor, question):
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
        )
    )

    # then remove old media in s3
    all_artifacts = ["original.mp4", "web.mp4", "mobile.mp4", "en.vtt"]
    s3_client.delete_objects(
        Bucket=s3_bucket,
        Delete={"Objects": [{"Key": f"{s3_path}/{name}"} for name in all_artifacts]},
    )

    s3_client.upload_file(
        file_path,
        s3_bucket,
        f"{s3_path}/original.mp4",
        ExtraArgs={"ContentType": "video/mp4"},
    )


def get_original_video_url(mentor: str, question: str) -> str:
    base_url = os.environ.get("STATIC_URL_BASE", "")
    return f"{base_url}/videos/{mentor}/{question}/original.mp4"


def handler(event, context):
    log.debug(json.dumps(event))
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

    mentor = upload_request["mentor"]
    question = upload_request["question"]
    video_key = upload_request["video"]
    trim = upload_request.get("trim")
    has_edited_transcript = upload_request.get("hasEditedTranscript")
    token = json.loads(event["requestContext"]["authorizer"]["token"])

    if not is_authorized(mentor, token):
        data = {
            "error": "not authorized",
            "message": "not authorized",
        }
        return create_json_response(401, data, event)
    upload_in_progress = is_upload_in_progress(FetchUploadTaskReq(mentor, question))
    if upload_in_progress:
        data = {
            "error": "upload in progress",
            "message": "There is an upload already in progress, please wait.",
        }
        return create_json_response(401, data, event)

    with tempfile.TemporaryDirectory() as work_dir:
        file_path = os.path.join(work_dir, "original.mp4")
        s3_client.download_file(upload_bucket, video_key, file_path)

        if not assert_video_duration(file_path, 1000):
            data = {
                "error": "Bad Request",
                "message": "No video found or too short (1sec)!",
            }
            return create_json_response(401, data, event)

        if trim:
            log.info("trimming file %s", trim)
            trim_file = f"{file_path}-trim.mp4"
            video_trim(
                file_path,
                trim_file,
                trim["start"],
                trim["end"],
            )
            file_path = trim_file  # from now on work with the trimmed file

        s3_path = f"videos/{mentor}/{question}"
        # this will overwrite any existing file
        upload_to_s3(file_path, s3_path, mentor, question)

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
            "video": f"{s3_path}/original.mp4",
            "transcodeWebTask": transcode_web_task,
            "transcodeMobileTask": transcode_mobile_task,
            "trimUploadTask": trim_upload_task,
            "transcribeTask": transcribe_task,
        }
    }

    original_video_url = get_original_video_url(mentor, question)
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
    )
    submit_job(req)

    data = {
        "taskList": task_list,
        "statusUrl": "use taskList to fetch from graphql",
    }
    return create_json_response(200, data, event)


# for local debugging:
if __name__ == "__main__":
    with open("__events__/answer-upload-event.json.dist") as f:
        event = json.loads(f.read())
        handler(event, {})
