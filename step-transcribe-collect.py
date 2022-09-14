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
from module.logger import get_logger
from module.api import (
    AnswerUpdateRequest,
    UpdateTaskStatusRequest,
    upload_answer_and_task_status_update,
)
from module.utils import (
    s3_bucket,
    load_sentry,
    require_env,
    fetch_from_graphql,
)


load_sentry()
s3 = boto3.client("s3")
log = get_logger("answer-transcribe-handler")
aws_region = require_env("REGION")
sfn_client = boto3.client("stepfunctions", region_name=aws_region)


def process_event(record, mentor, question, stored_task):
    key = record["s3"]["object"]["key"]
    s3_path = os.path.dirname(key)

    with tempfile.TemporaryDirectory() as work_dir:
        # since 2 files get dropped, there're 2 lambda invocations
        # its possible that not both files are in s3 when lambda runs for the first time

        try:
            job_file = os.path.join(work_dir, "transcribe.json")
            s3.download_file(
                record["s3"]["bucket"]["name"], f"{s3_path}/transcribe.json", job_file
            )
        except botocore.exceptions.ClientError as e:
            # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html
            if e.response["Error"]["Code"] == "404":
                log.info("failed to fetch transcribe json")
                return
            raise e
        with open(job_file, "r") as f:
            job = json.loads(f.read())
            transcript = job["results"]["transcripts"][0]["transcript"]
            log.debug(transcript)

        # If there is no transcript, then a vtt file will never be produced by the AWS transcription job, so we're done
        if transcript == "":
            log.debug("No transcript was produced, skipping check for vtt file")
            upload_answer_and_task_status_update(
                AnswerUpdateRequest(
                    mentor=mentor,
                    question=question,
                    transcript=transcript,
                    has_edited_transcript=False,
                ),
                UpdateTaskStatusRequest(
                    mentor=mentor,
                    question=question,
                    transcript=transcript,
                    transcribe_task={"status": "DONE"},
                ),
            )
            sfn_client.send_task_success(taskToken=stored_task["payload"], output="{}")

        try:
            vtt_file = os.path.join(work_dir, "transcribe.vtt")
            s3.download_file(
                record["s3"]["bucket"]["name"], f"{s3_path}/transcribe.vtt", vtt_file
            )
        except botocore.exceptions.ClientError as e:
            # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html
            if e.response["Error"]["Code"] == "404":
                log.info("failed to fetch subtitle vtt")
                return
            raise e

        s3.upload_file(
            vtt_file,
            s3_bucket,
            f"videos/{mentor}/{question}/en.vtt",
            ExtraArgs={"ContentType": "text/vtt"},
        )
        vtt_media = {
            "type": "subtitles",
            "tag": "en",
            "url": f"videos/{mentor}/{question}/en.vtt",
        }

        upload_answer_and_task_status_update(
            AnswerUpdateRequest(
                mentor=mentor,
                question=question,
                transcript=transcript,
                vtt_media=vtt_media,
                has_edited_transcript=False,
            ),
            UpdateTaskStatusRequest(
                mentor=mentor,
                question=question,
                transcript=transcript,
                transcribe_task={"status": "DONE"},
                vtt_media=vtt_media,
            ),
        )
        sfn_client.send_task_success(taskToken=stored_task["payload"], output="{}")


def handler(event, context):
    """This lambda is triggered with an S3 event - when the transcribe job is done,
    and NOT by the Step Function. Therefore it must in all scenarios report
    execution status back to the Step Function, otherwise the Step Function
    won't be able to continue execution.
    """
    log.info(event)
    for record in event["Records"]:
        key = record["s3"]["object"]["key"]
        s3_path = os.path.dirname(key)
        [mentor, question, *_] = s3_path.split("/")
        stored_task = fetch_from_graphql(mentor, question, task_name="transcribeTask")
        if not stored_task:
            log.warn(
                "task not found, cannot continue! step function will have to timeout"
            )
            return
        if stored_task["status"].startswith("CANCEL"):
            log.info("task cancelled, skipping transcription")
            sfn_client.send_task_success(taskToken=stored_task["payload"], output="{}")
            return

        try:
            process_event(record, mentor, question, stored_task)
        except Exception as err:
            log.error(err)
            sfn_client.send_task_failure(
                taskToken=stored_task["payload"],
                error=str(err),
                cause=str(err.__cause__),
            )
            raise err
