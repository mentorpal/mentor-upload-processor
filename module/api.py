#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
from dataclasses import dataclass
import json
from os import environ
from typing import TypedDict, List
import requests
from module.logger import get_logger


log = get_logger()


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


@dataclass
class MentorThumbnailUpdateRequest:
    mentor: str
    thumbnail: str


@dataclass
class FetchUploadTaskReq:
    mentor: str
    question: str


class GQLQueryBody(TypedDict):
    query: str


@dataclass
class ImportTaskCreateGraphQLUpdate:
    status: str
    errorMessage: str = ""  # noqa


@dataclass
class AnswerMediaMigrationTask:
    question: str
    status: str
    errorMessage: str = ""  # noqa


@dataclass
class ImportTaskCreateS3VideoMigration:
    status: str
    answerMediaMigrations: List[AnswerMediaMigrationTask]  # noqa


@dataclass
class ImportTaskGQLRequest:
    mentor: str
    graphql_update: ImportTaskCreateGraphQLUpdate
    s3_video_migration: ImportTaskCreateS3VideoMigration


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


def fetch_upload_task_gql(req: FetchUploadTaskReq) -> GQLQueryBody:
    return {
        "query": """query UploadTask($mentorId: ID!, $questionId: ID!) {
            uploadTask(mentorId: $mentorId, questionId: $questionId){
                transcript
            }
            }""",
        "variables": {"mentorId": req.mentor, "questionId": req.question},
    }


def is_upload_in_progress(req: FetchUploadTaskReq) -> bool:
    headers = {"mentor-graphql-req": "true", "Authorization": f"bearer {get_api_key()}"}
    body = fetch_upload_task_gql(req)
    log.debug(body)
    res = requests.post(get_graphql_endpoint(), json=body, headers=headers)
    res.raise_for_status()
    tdjson = res.json()
    # TODO validate_json(tdjson, fetch_upload_task_schema)
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))
    return bool(tdjson["data"]["uploadTask"])


def thumbnail_update_gql(req: MentorThumbnailUpdateRequest) -> GQLQueryBody:
    return {
        "query": """mutation MentorThumbnailUpdate($mentorId: ID!, $thumbnail: String!) {
            api {
                mentorThumbnailUpdate(mentorId: $mentorId, thumbnail: $thumbnail)
            }
        }""",
        "variables": {"mentorId": req.mentor, "thumbnail": req.thumbnail},
    }


def mentor_thumbnail_update(req: MentorThumbnailUpdateRequest) -> None:
    headers = {"mentor-graphql-req": "true", "Authorization": f"bearer {get_api_key()}"}
    body = thumbnail_update_gql(req)
    log.debug(body)
    res = requests.post(get_graphql_endpoint(), json=body, headers=headers)
    res.raise_for_status()
    tdjson = res.json()
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))


def import_task_create_gql_query(req: ImportTaskGQLRequest) -> GQLQueryBody:
    return {
        "query": """mutation ImportTaskCreate($mentor: ID!,
        $graphQLUpdate: GraphQLUpdateInputType!,
        $s3VideoMigrate: S3VideoMigrationInputType!) {
            api {
                importTaskCreate(graphQLUpdate: $graphQLUpdate, mentor: $mentor, s3VideoMigrate: $s3VideoMigrate)
            }
        }""",
        "variables": {
            "mentor": req.mentor,
            "graphQLUpdate": req.graphql_update,
            "s3VideoMigrate": req.s3_video_migration,
        },
    }


def import_task_create_gql(req: ImportTaskGQLRequest) -> None:
    headers = {"mentor-graphql-req": "true", "Authorization": f"bearer {get_api_key()}"}
    body = import_task_create_gql_query(req)
    res = requests.post(get_graphql_endpoint(), json=body, headers=headers)
    res.raise_for_status()
    tdjson = res.json()
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))
