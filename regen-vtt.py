import json
import base64
import tempfile
import os
from module.api import fetch_answer_transcript_and_media
from media_tools import transcript_to_vtt
import boto3
from module.logger import get_logger
from module.utils import create_json_response, s3_bucket, load_sentry

s3 = boto3.client("s3")

load_sentry()
log = get_logger("regen-vtt")


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
    regen_vtt_request = json.loads(body)
    if "mentor" not in regen_vtt_request:
        data = {
            "error": "Bad Request",
            "message": "mentor parameter missing",
        }
        return create_json_response(401, data, event)
    if "question" not in regen_vtt_request:
        data = {
            "error": "Bad Request",
            "message": "question parameter missing",
        }
        return create_json_response(401, data, event)
    mentor = regen_vtt_request["mentor"]
    question = regen_vtt_request["question"]
    with tempfile.TemporaryDirectory() as tmp_dir:
        vtt_file_path = os.path.join(tmp_dir, "en.vtt")
        (
            transcript,
            video_media,
        ) = fetch_answer_transcript_and_media(mentor, question)
        transcript_to_vtt(video_media["url"], vtt_file_path, transcript)
        if os.path.isfile(vtt_file_path):
            item_path = f"videos/{mentor}/{question}/en.vtt"
            s3.upload_file(
                str(vtt_file_path),
                s3_bucket,
                item_path,
                ExtraArgs={"ContentType": "text/vtt"},
            )
        else:
            raise Exception(f"Failed to find vtt file at {vtt_file_path}")
        data = {"regen_vtt": True}
        return create_json_response(200, data, event)
