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
from media_tools import video_to_audio, has_audio
from api import (
    UpdateTaskStatusRequest,
    fetch_question_name,
    upload_task_status_update,
    fetch_task,
)


log = logger.get_logger("answer-transcribe-start-handler")


if os.environ.get("IS_SENTRY_ENABLED", "") == "true":
    log.info("SENTRY enabled, calling init")
    import sentry_sdk  # NOQA E402
    from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration  # NOQA E402

    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN_MENTOR_UPLOAD"),
        # include project so issues can be filtered in sentry:
        environment=os.environ.get("PYTHON_ENV", "careerfair-qa"),
        integrations=[AwsLambdaIntegration(timeout_warning=True)],
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=0.20,
        debug=os.environ.get("SENTRY_DEBUG_UPLOADER", "") == "true",
    )


def _require_env(n: str) -> str:
    env_val = os.environ.get(n, "")
    if not env_val:
        raise EnvironmentError(f"missing required env var {n}")
    return env_val


aws_region = os.environ.get('AWS_REGION','us-east-1')
s3_bucket = _require_env("S3_STATIC_ARN").split(":")[-1]
log.info("using s3 bucket %s", s3_bucket)
input_bucket = _require_env("TRANSCRIBE_INPUT_BUCKET")
output_bucket = _require_env("TRANSCRIBE_OUTPUT_BUCKET")
s3 = boto3.client("s3")
transcribe = boto3.client("transcribe", region_name=aws_region)


def is_idle_question(question_id: str) -> bool:
    name = fetch_question_name(question_id)
    return name == "_IDLE_"


def transcribe_video(mentor, question, task_id, video_file):
    if not has_audio(video_file):
        log.warn('video file does not contain any audio streams')
        # continue to overwrite any existing previous transcript
    else:
        audio_file = video_to_audio(video_file) # fails if no audio stream exists
        log.info("transcribing %s", audio_file)
      
        input_s3_path = f"{mentor}/{question}/${task_id}/answer.mp3"
        s3.upload_file(
            audio_file,
            input_bucket,
            input_s3_path,
            ExtraArgs={"ContentType": "audio/mp3"},
        )
        job = transcribe.start_transcription_job(
            TranscriptionJobName=f"{mentor}_{question}_{task_id}",
            LanguageCode="en-US",
            Media={
                "MediaFileUri": f"https://s3.{aws_region}.amazonaws.com/{input_bucket}/{input_s3_path}"
            },
            MediaFormat="mp3",
            OutputBucketName=output_bucket,
            OutputKey=f"{mentor}/{question}/{task_id}/transcribe.json",
            Subtitles={
                "Formats":["vtt"]
            }
        )
        log.info(job)
# {'TranscriptionJob': {'TranscriptionJobName': '61ef5df326c18b5437c52612_607766dec525ba87bf68e79b_f1163c07-bc9a-432c-8829-1861f0a5a7c6', 'TranscriptionJobStatus': 'IN_PROGRESS', 'LanguageCode': 'en-US', 'MediaFormat': 'mp3', 'Media': {'MediaFileUri': 'https://s3.us-east-1.amazonaws.com/mentorpal-upload-sm-transcribe-input-dev/61ef5df326c18b5437c52612/607766dec525ba87bf68e79b/$f1163c07-bc9a-432c-8829-1861f0a5a7c6/answer.mp3'}, 'StartTime': datetime.datetime(2022, 2, 2, 14, 46, 14, 649000, tzinfo=tzlocal()), 'CreationTime': datetime.datetime(2022, 2, 2, 14, 46, 14, 626000, tzinfo=tzlocal()), 'Subtitles': {'Formats': ['vtt']}}, 'ResponseMetadata': {'RequestId': 'a845ff03-f074-4ef4-9cc5-456c82569c63', 'HTTPStatusCode': 200, 'HTTPHeaders': {'content-type': 'application/x-amz-json-1.1', 'date': 'Wed, 02 Feb 2022 13:46:14 GMT', 'x-amzn-requestid': 'a845ff03-f074-4ef4-9cc5-456c82569c63', 'content-length': '511', 'connection': 'keep-alive'}, 'RetryAttempts': 0}}

def fetch_from_graphql(request, task):
    upload_task = fetch_task(request["mentor"], request["question"])
    if not upload_task:
        # this can happen if any task_list status is failed and client deletes the task
        return None
    stored_task = next(
        (x for x in upload_task["taskList"] if x["task_id"] == task["task_id"]),
        None,
    )
    if stored_task is None:
        log.error("task it doesnt match %s %s", task, upload_task["taskList"])
        raise Exception(
            "task it doesnt match %s %s",
            task["task_id"],
            [t["task_id"] for t in upload_task["taskList"]],
        )
    return stored_task


def process_task(request, task):
    stored_task = fetch_from_graphql(request, task)
    if not stored_task:
        log.warn("task not found, skipping transcription")
        return
    if stored_task["status"].startswith("CANCEL"):
        log.info("task cancelled, skipping transcription")
        return

    is_idle = is_idle_question(request["question"])
    if is_idle:
        log.info("question is idle, nothing to transcribe")
        upload_task_status_update(
            UpdateTaskStatusRequest(
                mentor=request["mentor"],
                question=request["question"],
                task_id=task["task_id"],
                new_status="DONE",
            )
        )
        return

    upload_task_status_update(
        UpdateTaskStatusRequest(
            mentor=request["mentor"],
            question=request["question"],
            task_id=task["task_id"],
            new_status="IN_PROGRESS",
        )
    )

    log.info("video to process %s", request["video"])
    with tempfile.TemporaryDirectory() as work_dir:
        work_file = os.path.join(work_dir, "original.mp4")
        s3.download_file(s3_bucket, request["video"], work_file)
        log.info("%s downloaded to %s", request["video"], work_dir)

        transcribe_video(
            request["mentor"],
            request["question"],
            task["task_id"],
            work_file,
        )


def handler(event, context):
    log.info(json.dumps(event))
    for record in event["Records"]:
        body = json.loads(str(record["body"]))
        request = json.loads(str(body["Message"]))["request"]
        task_list = request["task_list"]
        task = next(filter(lambda t: t["task_name"] == "transcribing", task_list))
        if not task:
            log.warning("transcribe task not requested")
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

# for local debugging:
# if __name__ == '__main__':
#     with open('./__events__/answer-event.json.dist') as f:
#         event = json.loads(f.read())
#         handler(event, {})
