#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
from module.logger import get_logger
from dataclasses import dataclass
import json
from os import environ
from typing import TypedDict

import requests
import jsonschema

log = get_logger("api")


def get_graphql_endpoint() -> str:
    return environ.get("GRAPHQL_ENDPOINT") or "http://graphql/graphql"


def get_api_key() -> str:
    return environ.get("API_SECRET") or ""


@dataclass
class Media:
    type: str
    tag: str
    url: str
    needsTransfer: bool  # noqa: N815


@dataclass
class TaskInfo:
    task_id: str
    status: str


@dataclass
class AnswerUpdateRequest:
    mentor: str
    question: str
    web_media: Media = None
    mobile_media: Media = None
    vtt_media: Media = None
    transcript: str = None
    has_edited_transcript: bool = None


@dataclass
class UpdateTaskStatusRequest:
    mentor: str
    question: str
    transcript: str = None
    transcode_web_task: TaskInfo = None
    transcode_mobile_task: TaskInfo = None
    transcribe_task: TaskInfo = None
    web_media: Media = None
    mobile_media: Media = None
    vtt_media: Media = None


@dataclass
class AnswerUpdateResponse:
    mentor: str
    question: str
    transcript: str
    web_media: Media
    mobile_media: Media
    vtt_media: Media


class GQLQueryBody(TypedDict):
    query: str


def fetch_question_name_gql(question_id: str) -> GQLQueryBody:
    return {
        "query": """query Question($id: ID!) {
            question(id: $id){
                name
            }
        }""",
        "variables": {
            "id": question_id,
        },
    }


def fetch_task_gql(mentor_id: str, question_id) -> GQLQueryBody:
    return {
        "query": """query UploadTask($mentorId: ID!, $questionId: ID!) {
            uploadTask(mentorId: $mentorId, questionId: $questionId){
                transcodeWebTask {
                    task_id
                    status
                }
                transcodeMobileTask {
                    task_id
                    status
                }
                transcribeTask{
                    task_id
                    status
                }
            }
        }""",
        "variables": {
            "mentorId": mentor_id,
            "questionId": question_id,
        },
    }


def fetch_task(mentor_id: str, question_id) -> dict:
    headers = {"mentor-graphql-req": "true", "Authorization": f"bearer {get_api_key()}"}
    body = fetch_task_gql(mentor_id, question_id)
    res = requests.post(
        get_graphql_endpoint(), json=body, headers=headers, verify=False
    )
    res.raise_for_status()
    tdjson = res.json()
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))
    return tdjson["data"]["uploadTask"]


def fetch_question_name(question_id: str) -> str:
    headers = {"mentor-graphql-req": "true", "Authorization": f"bearer {get_api_key()}"}
    body = fetch_question_name_gql(question_id)
    res = requests.post(
        get_graphql_endpoint(), json=body, headers=headers, verify=False
    )
    res.raise_for_status()
    tdjson = res.json()
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))
    if (
        "data" not in tdjson
        or "question" not in tdjson["data"]
        or "name" not in tdjson["data"]["question"]
    ):
        raise Exception(f"query: {body} did not return proper data format")
    return tdjson["data"]["question"]["name"]


def upload_task_status_req_gql(req: UpdateTaskStatusRequest) -> GQLQueryBody:
    variables = {"mentorId": req.mentor, "questionId": req.question}

    variables["uploadTaskStatusInput"] = {}
    if req.transcript:
        variables["uploadTaskStatusInput"]["transcript"] = req.transcript
    if req.transcode_web_task:
        variables["uploadTaskStatusInput"]["transcodeWebTask"] = req.transcode_web_task
    if req.transcode_mobile_task:
        variables["uploadTaskStatusInput"][
            "transcodeMobileTask"
        ] = req.transcode_mobile_task
    if req.transcribe_task:
        variables["uploadTaskStatusInput"]["transcribeTask"] = req.transcribe_task

    if req.web_media:
        variables["uploadTaskStatusInput"]["webMedia"] = req.web_media
    if req.mobile_media:
        variables["uploadTaskStatusInput"]["mobileMedia"] = req.mobile_media
    if req.vtt_media:
        variables["uploadTaskStatusInput"]["vttMedia"] = req.vtt_media

    return {
        "query": """mutation UpdateUploadTaskStatus($mentorId: ID!, $questionId: ID!, $uploadTaskStatusInput: UploadTaskStatusUpdateInputType!) {
            api {
                uploadTaskStatusUpdate(mentorId: $mentorId, questionId: $questionId, uploadTaskStatusInput: $uploadTaskStatusInput)
            }
        }""",
        "variables": variables,
    }


def upload_answer_and_task_status_req_gql(
    answer_req: AnswerUpdateRequest, status_req: UpdateTaskStatusRequest
) -> GQLQueryBody:
    variables = {}
    variables["mentorId"] = answer_req.mentor
    variables["questionId"] = answer_req.question
    variables["answer"] = {}
    if answer_req.transcript is not None:
        variables["answer"]["transcript"] = answer_req.transcript
    if answer_req.has_edited_transcript is not None:
        variables["answer"]["hasEditedTranscript"] = answer_req.has_edited_transcript
    if answer_req.vtt_media:
        variables["answer"]["vttMedia"] = answer_req.vtt_media
    if answer_req.web_media:
        variables["answer"]["webMedia"] = answer_req.web_media
    if answer_req.mobile_media:
        variables["answer"]["mobileMedia"] = answer_req.mobile_media

    variables["uploadTaskStatusInput"] = {}
    if status_req.transcript is not None:
        variables["uploadTaskStatusInput"]["transcript"] = status_req.transcript
    if status_req.transcode_web_task:
        variables["uploadTaskStatusInput"][
            "transcodeWebTask"
        ] = status_req.transcode_web_task
    if status_req.transcode_mobile_task:
        variables["uploadTaskStatusInput"][
            "transcodeMobileTask"
        ] = status_req.transcode_mobile_task
    if status_req.transcribe_task:
        variables["uploadTaskStatusInput"][
            "transcribeTask"
        ] = status_req.transcribe_task
    if status_req.vtt_media:
        variables["uploadTaskStatusInput"]["vttMedia"] = status_req.vtt_media
    if status_req.web_media:
        variables["uploadTaskStatusInput"]["webMedia"] = status_req.web_media
    if status_req.mobile_media:
        variables["uploadTaskStatusInput"]["mobileMedia"] = status_req.mobile_media

    return {
        "query": """mutation UpdateUploadAnswerAndTaskStatus($mentorId: ID!, $questionId: ID!, $answer: UploadAnswerType!, $uploadTaskStatusInput: UploadTaskStatusUpdateInputType!) {
            api {
                uploadAnswer(mentorId: $mentorId, questionId: $questionId, answer: $answer)
                uploadTaskStatusUpdate(mentorId: $mentorId, questionId: $questionId, uploadTaskStatusInput: $uploadTaskStatusInput)
            }
        }""",
        "variables": variables,
    }


def upload_answer_and_task_status_update(
    answer_req: AnswerUpdateRequest, status_req: UpdateTaskStatusRequest
) -> None:
    headers = {"mentor-graphql-req": "true", "Authorization": f"bearer {get_api_key()}"}
    body = upload_answer_and_task_status_req_gql(answer_req, status_req)
    res = requests.post(
        get_graphql_endpoint(), json=body, headers=headers, verify=False
    )
    res.raise_for_status()
    tdjson = res.json()
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))


def upload_task_status_update(req: UpdateTaskStatusRequest) -> None:
    headers = {"mentor-graphql-req": "true", "Authorization": f"bearer {get_api_key()}"}
    body = upload_task_status_req_gql(req)
    res = requests.post(
        get_graphql_endpoint(), json=body, headers=headers, verify=False
    )
    res.raise_for_status()
    tdjson = res.json()
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))


def validate_json(json_data, json_schema):
    try:
        jsonschema.validate(instance=json_data, schema=json_schema)
    except jsonschema.exceptions.ValidationError as err:
        log.error(msg=err)
        raise Exception(err)


def exec_graphql_with_json_validation(request_query, json_schema, **req_kwargs):
    res = requests.post(get_graphql_endpoint(), json=request_query, **req_kwargs)
    res.raise_for_status()
    tdjson = res.json()
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))
    validate_json(tdjson, json_schema)
    return tdjson


fetch_answer_transcript_media_json_schema = {
    "type": "object",
    "properties": {
        "data": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "object",
                    "properties": {
                        "transcript": {"type": "string"},
                        "webMedia": {
                            "type": ["object", "null"],
                            "properties": {
                                "type": {"type": "string"},
                                "tag": {"type": "string"},
                                "url": {"type": "string"},
                            },
                        },
                        "mobileMedia": {
                            "type": ["object", "null"],
                            "properties": {
                                "type": {"type": "string"},
                                "tag": {"type": "string"},
                                "url": {"type": "string"},
                            },
                        },
                    },
                    "required": ["transcript", "webMedia", "mobileMedia"],
                }
            },
            "required": ["answer"],
        },
    },
    "required": ["data"],
}


def fetch_answer_transcript_and_media_gql(mentor: str, question: str) -> GQLQueryBody:
    return {
        "query": """query Answer($mentor: ID!, $question: ID!) {
            answer(mentor: $mentor, question: $question){
                transcript
                webMedia {
                    type
                    tag
                    url
                }
                mobileMedia{
                    type
                    tag
                    url
                }
            }
        }""",
        "variables": {"mentor": mentor, "question": question},
    }


def fetch_answer_transcript_and_media(mentor: str, question: str):
    headers = {"mentor-graphql-req": "true", "Authorization": f"bearer {get_api_key()}"}
    gql_query = fetch_answer_transcript_and_media_gql(mentor, question)
    json_res = exec_graphql_with_json_validation(
        gql_query, fetch_answer_transcript_media_json_schema, headers=headers
    )
    answer_data = json_res["data"]["answer"]
    web_media = answer_data["webMedia"]
    mobile_media = answer_data["mobileMedia"]
    transcript = answer_data["transcript"]
    if web_media is None and mobile_media is None:
        raise Exception(
            f"No video media found for mentor {mentor} and question {question}"
        )
    return (transcript, web_media or mobile_media)
