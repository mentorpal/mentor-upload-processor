#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
import json
import boto3
import botocore
import tempfile
import os
import logger
from api import (
    AnswerUpdateRequest,
    UpdateTaskStatusRequest,
    upload_task_status_update,
    upload_answer_and_task_status_update,
)
from util import s3_bucket, load_sentry, fetch_from_graphql


load_sentry()
s3 = boto3.client("s3")
log = logger.get_logger("answer-transcribe-handler")


def process_event(record):
    key = record["s3"]["object"]["key"]
    s3_path = os.path.dirname(key)
    [mentor, question, task_id] = s3_path.split("/")
    stored_task = fetch_from_graphql(mentor, question, task_id)
    if not stored_task:
        log.warn("task not found, skipping")
        return
    if stored_task["status"].startswith("CANCEL"):
        log.info("task cancelled, skipping transcription")
        return

    with tempfile.TemporaryDirectory() as work_dir:
        # since 2 files get dropped, there're 2 lambda invocations
        # its possible that not both files are in s3 when lambda runs first time
        try:
            job_file = os.path.join(work_dir, "transcribe.json")
            s3.download_file(
                record["s3"]["bucket"]["name"], f"{s3_path}/transcribe.json", job_file
            )
            vtt_file = os.path.join(work_dir, "transcribe.vtt")
            s3.download_file(
                record["s3"]["bucket"]["name"], f"{s3_path}/transcribe.vtt", vtt_file
            )
        except botocore.exceptions.ClientError as e:
            # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html
            if e.response["Error"]["Code"] == "404":
                # on the second invocation both files will be present so this should not happen twice
                log.info("failed to fetch transcript and subtitle")
                return
            raise e

        with open(job_file, "r") as f:
            job = json.loads(f.read())
            transcript = job["results"]["transcripts"][0]["transcript"]
            log.debug(transcript)
        s3.upload_file(
            vtt_file,
            s3_bucket,
            f"videos/{mentor}/{question}/en.vtt",
            ExtraArgs={"ContentType": "text/vtt"},
        )
        media = [
            {
                "type": "subtitles",
                "tag": "en",
                "url": f"videos/{mentor}/{question}/en.vtt",
            }
        ]

        upload_answer_and_task_status_update(
            AnswerUpdateRequest(
                mentor=mentor,
                question=question,
                transcript=transcript,
                media=media,
                has_edited_transcript=False,
            ),
            UpdateTaskStatusRequest(
                mentor=mentor,
                question=question,
                transcript=transcript,
                task_id=task_id,
                new_status="DONE",
                media=media,
            ),
        )


def handler(event, context):
    log.info(json.dumps(event))
    for record in event["Records"]:
        try:
            process_event(record)
        except Exception as x:
            key = record["s3"]["object"]["key"]
            s3_path = os.path.dirname(key)
            [mentor, question, task_id] = s3_path.split("/")
            upload_task_status_update(
                UpdateTaskStatusRequest(
                    mentor=mentor,
                    question=question,
                    task_id=task_id,
                    new_status="FAILED",
                )
            )
            raise x


# # for local debugging:
# if __name__ == '__main__':
#     with open('__events__/transcribe-collect-event.json.dist') as f:
#         event = json.loads(f.read())
#         handler(event, {})
