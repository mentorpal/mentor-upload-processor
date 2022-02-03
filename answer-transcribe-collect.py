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
from api import (
    AnswerUpdateRequest,
    UpdateTaskStatusRequest,
    upload_task_status_update,
    upload_answer_and_task_status_update,
    fetch_task,
)


log = logger.get_logger("answer-transcribe-handler")


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


s3_bucket = _require_env("S3_STATIC_ARN").split(":")[-1]
log.info("using s3 bucket %s", s3_bucket)
s3 = boto3.client("s3")



def fetch_from_graphql(mentor, question, task_id):
    upload_task = fetch_task(mentor, question)
    if not upload_task:
        # this can happen if any task_list status is failed and client deletes the task
        return None
    stored_task = next(
        (x for x in upload_task["taskList"] if x["task_id"] == task_id),
        None,
    )
    if stored_task is None:
        log.error("task it doesnt match %s %s", task_id, upload_task["taskList"])
        raise Exception(
            "task it doesnt match %s %s",
            task_id,
            [t["task_id"] for t in upload_task["taskList"]],
        )
    return stored_task


def process_event(record):
    key = record["s3"]["object"]["key"]
    s3_path = os.path.dirname(key)
    [mentor, question, task_id] = s3_path.split('/')
    stored_task = fetch_from_graphql(mentor, question, task_id)
    if not stored_task:
        log.warn("task not found, skipping")
        return
    if stored_task["status"].startswith("CANCEL"):
        log.info("task cancelled, skipping transcription")
        return

    with tempfile.TemporaryDirectory() as work_dir:        
        try:
            job_file = os.path.join(work_dir, 'transcribe.json')
            s3.download_file(record['s3']['bucket']['name'], f"{s3_path}/transcribe.json", job_file)
            vtt_file = os.path.join(work_dir, 'transcribe.vtt')
            s3.download_file(record['s3']['bucket']['name'], f"{s3_path}/transcribe.vtt", vtt_file)
        except Exception as e:
            log.info('failed to download one artifact: {}', e)
            return
        
        with open(job_file, 'r') as f:
            job = json.loads(f.read())
            transcript = job["results"]["transcripts"][0]["transcript"]
            log.debug(transcript)
        s3.upload_file(
            vtt_file,
            s3_bucket,
            f"{s3_path}/en.vtt", # same path, different bucket!
            ExtraArgs={"ContentType": "text/vtt"},
        )
        media = [
            {
                "type": "subtitles",
                "tag": "en",
                "url": f"{s3_path}/en.vtt",
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
            [mentor, question, task_id] = s3_path.split('/')
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
#     with open('./__events__/transcribe-collect-event.json.dist') as f:
#         event = json.loads(f.read())
#         handler(event, {})