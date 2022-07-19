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
import uuid
from media_tools import video_to_audio, has_audio
from api import (
    UpdateTaskStatusRequest,
    fetch_question_name,
    upload_task_status_update,
)
from util import s3_bucket, require_env, load_sentry, fetch_from_graphql

load_sentry()
log = logger.get_logger("answer-transcribe-start-handler")

aws_region = require_env("REGION")
input_bucket = require_env("TRANSCRIBE_INPUT_BUCKET")
output_bucket = require_env("TRANSCRIBE_OUTPUT_BUCKET")
s3 = boto3.client("s3")
transcribe = boto3.client("transcribe", region_name=aws_region)
sfn_client = boto3.client("stepfunctions", region_name=aws_region)


def is_idle_question(question_id: str) -> bool:
    name = fetch_question_name(question_id)
    return name == "_IDLE_"


def transcribe_video(mentor, question, task_id, video_file):
    if not has_audio(video_file):  # this does not work on mac :/
        log.warn("video file does not contain any audio streams")
        # continue to overwrite any existing previous transcript
    else:
        audio_file = video_to_audio(video_file)  # fails if no audio stream exists
        log.info("transcribing %s", audio_file)

        input_s3_path = f"{mentor}/{question}/${task_id}/answer.mp3"
        s3.upload_file(
            audio_file,
            input_bucket,
            input_s3_path,
            ExtraArgs={"ContentType": "audio/mp3"},
        )
        job = transcribe.start_transcription_job(
            TranscriptionJobName=f"{mentor}_{question}_{task_id}_{uuid.uuid4()}",  # make sure job id is unique
            LanguageCode="en-US",
            Media={
                "MediaFileUri": f"https://s3.{aws_region}.amazonaws.com/{input_bucket}/{input_s3_path}"
            },
            MediaFormat="mp3",
            OutputBucketName=output_bucket,
            OutputKey=f"{mentor}/{question}/{task_id}/transcribe.json",
            Subtitles={"Formats": ["vtt"]},
            Settings={
                "ShowSpeakerLabels": False,
                "ChannelIdentification": False,  # process only one audio channel
                "ShowAlternatives": False,
            },
        )
        log.info(job)


def process_task(request, task):
    stored_task = fetch_from_graphql(
        request["mentor"], request["question"], "transcribeTask"
    )
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
                transcribe_task={"status": "DONE"},
            )
        )
        return

    upload_task_status_update(
        UpdateTaskStatusRequest(
            mentor=request["mentor"],
            question=request["question"],
            transcribe_task={"status": "IN_PROGRESS"},
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
    sfn_client.send_task_success(taskToken=event["task_token"], output="{}")

    # for record in event["Records"]:
    #     body = json.loads(str(record["body"]))
    #     request = json.loads(str(body["Message"]))["request"]
    #     task = request["transcribeTask"] if "transcribeTask" in request else None
    #     if not task:
    #         log.warning("transcribe task not requested")
    #         return

    #     try:
    #         process_task(request, task)
    #     except Exception as x:
    #         log.error(x)
    #         upload_task_status_update(
    #             UpdateTaskStatusRequest(
    #                 mentor=request["mentor"],
    #                 question=request["question"],
    #                 transcribe_task={"status": "FAILED"},
    #             )
    #         )
    #         raise x


# # for local debugging:
# if __name__ == '__main__':
#     with open('__events__/answer-event.json.dist') as f:
#         event = json.loads(f.read())
#         handler(event, {})
