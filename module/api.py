# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
#
from dataclasses import dataclass
import json
from os import environ
from typing import TypedDict, List, Dict
import requests
from module.logger import get_logger
import jsonschema


log = get_logger("graphql-api")


def get_graphql_endpoint() -> str:
    return environ.get("GRAPHQL_ENDPOINT") or "http://graphql/graphql"


SECRET_HEADER_NAME = environ.get("SECRET_HEADER_NAME")
SECRET_HEADER_VALUE = environ.get("SECRET_HEADER_VALUE")


@dataclass
class Media:
    type: str
    tag: str
    url: str
    needsTransfer: bool  # noqa: N815
    transparentVideoUrl: str = None  # noqa: N815


@dataclass
class TaskInfo:
    task_id: str
    status: str
    payload: str


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
    trim_upload_task: TaskInfo = None
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
class MentorVbgUpdateRequest:
    mentor: str
    vbgPath: str


@dataclass
class OrgHeaderUpdateRequest:
    imgPath: str
    orgId: str = None


@dataclass
class OrgFooterUpdateRequest:
    imgPath: str
    imgIdx: int
    orgId: str = None


@dataclass
class FetchUploadTaskReq:
    mentor: str
    question: str


@dataclass
class MediaUpdateRequest:
    mentor: str
    question: str
    web_media: Media = None
    mobile_media: Media = None
    vtt_media: Media = None


class GQLQueryBody(TypedDict):
    query: str


@dataclass
class ImportTaskCreateGraphQLUpdate:
    status: str
    errorMessage: str = ""  # noqa


@dataclass
class ImportTaskCreateS3VideoMigration:
    status: str
    errorMessage: str


@dataclass
class ImportTaskGQLRequest:
    mentor: str
    graphql_update: ImportTaskCreateGraphQLUpdate
    s3_video_migration: ImportTaskCreateS3VideoMigration


class MentorInfo:
    name: str
    firstName: str
    title: str
    email: str
    thumbnail: str
    allowContact: bool
    defaultSubject: str
    mentorType: str


class Question:
    _id: str
    question: str
    type: str
    name: str
    clientId: str
    paraphrases: List[str]
    mentor: str
    mentorType: str
    minVideoLength: str


class Category:
    id: str
    name: str
    description: str


class Topic:
    id: str
    name: str
    description: str


class SubjectQuestionGQL:
    question: Question
    category: Category
    topics: List[Topic]


class Subject:
    _id: str
    name: str
    type: str
    description: str
    isRequired: str
    categories: List[Category]
    topics: List[Topic]
    questions: List[SubjectQuestionGQL]


class ExternalVideoIds:
    wistiaId: str


class Answer:
    _id: str
    question: Question
    hasEditedTranscript: bool
    transcript: str
    status: str
    media: List[Media]
    externalVideoIds: ExternalVideoIds


class UserQuestionMentor:
    _id: str
    name: str


class UserQuestionQuestion:
    _id: str
    question: str


class UserQuestionAnswer:
    _id: str
    transcript: str
    question: UserQuestionQuestion


class UserQuestion:
    _id: str
    question: str
    confidence: float
    classifierEntryType: str
    feedback: str
    mentor: UserQuestionMentor
    classifierAnswer: UserQuestionAnswer
    graderAnswer: UserQuestionAnswer


class MentorExportJson:
    id: str
    mentorInfo: MentorInfo
    subjects: List[Subject]
    questions: List[Question]
    answers: List[Answer]
    userQuestions: List[UserQuestion]


class AnswerGQL:
    _id: str
    question: Question
    hasEditedTranscript: bool
    transcript: str
    status: str
    media: List[Media]
    hasUntransferredMedia: bool


class ReplacedMentorQuestionChanges:
    editType: str
    data: Question


class ReplacedMentorAnswerChanges:
    editType: str
    data: AnswerGQL


class ReplacedMentorDataChanges:
    questionChanges: List[ReplacedMentorQuestionChanges]
    answerChanges: List[ReplacedMentorAnswerChanges]


class ProcessTransferMentor(TypedDict):
    mentor: str
    mentorExportJson: MentorExportJson
    replacedMentorDataChanges: List[ReplacedMentorDataChanges]


@dataclass
class ImportTaskUpdateGQLRequest:
    mentor: str
    migration_errors: List[str] = None
    graphql_update: ImportTaskCreateGraphQLUpdate = None
    s3_video_migration: ImportTaskCreateS3VideoMigration = None


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
                    payload
                }
                trimUploadTask{
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


def __auth_gql(query: GQLQueryBody, headers: Dict[str, str] = {}) -> dict:
    final_headers = {**headers, f"{SECRET_HEADER_NAME}": f"{SECRET_HEADER_VALUE}"}
    # SSL is not valid for alb so have to turn off validation
    res = requests.post(get_graphql_endpoint(), json=query, headers=final_headers)
    res.raise_for_status()
    return res.json()


def fetch_task(mentor_id: str, question_id, headers: Dict[str, str] = {}) -> dict:
    body = fetch_task_gql(mentor_id, question_id)
    tdjson = __auth_gql(body, headers)
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))
    return tdjson["data"]["uploadTask"]


def fetch_question_name(question_id: str, headers: Dict[str, str] = {}) -> str:
    body = fetch_question_name_gql(question_id)
    tdjson = __auth_gql(body, headers)
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
    if req.trim_upload_task:
        variables["uploadTaskStatusInput"]["trimUploadTask"] = req.trim_upload_task
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
    answer_req: AnswerUpdateRequest,
    status_req: UpdateTaskStatusRequest,
    headers: Dict[str, str] = {},
) -> None:
    body = upload_answer_and_task_status_req_gql(answer_req, status_req)
    tdjson = __auth_gql(body, headers)
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))


def upload_task_status_update(
    req: UpdateTaskStatusRequest, headers: Dict[str, str] = {}
) -> None:
    body = upload_task_status_req_gql(req)
    tdjson = __auth_gql(body, headers)
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


def is_upload_in_progress(
    req: FetchUploadTaskReq, headers: Dict[str, str] = {}
) -> bool:
    body = fetch_upload_task_gql(req)
    log.debug(body)
    tdjson = __auth_gql(body, headers)
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


def mentor_thumbnail_update(
    req: MentorThumbnailUpdateRequest, headers: Dict[str, str] = {}
) -> None:
    body = thumbnail_update_gql(req)
    log.debug(body)
    tdjson = __auth_gql(body, headers)
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))


def vbg_update_gql(req: MentorVbgUpdateRequest) -> GQLQueryBody:
    return {
        "query": """mutation MentorVbgUpdate($mentorId: ID!, $vbgPath: String!) {
          api {
            mentorVbgUpdate(mentorId: $mentorId, vbgPath: $vbgPath)
          }
        }""",
        "variables": {"mentorId": req.mentor, "vbgPath": req.vbgPath},
    }


def mentor_vbg_update(
    req: MentorVbgUpdateRequest, headers: Dict[str, str] = {}
) -> None:
    body = vbg_update_gql(req)
    log.debug(body)
    tdjson = __auth_gql(body, headers)
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))


def org_header_update_gql(req: OrgHeaderUpdateRequest) -> GQLQueryBody:
    variables = {"imgPath": req.imgPath}
    if req.orgId:
        variables["orgId"] = req.orgId
    return {
        "query": """mutation OrgHeaderUpdate($orgId: ID, $imgPath: String!) {
          api {
            orgHeaderUpdate(orgId: $orgId, imgPath: $imgPath)
          }
        }""",
        "variables": variables,
    }


def org_header_update(
    req: OrgHeaderUpdateRequest, headers: Dict[str, str] = {}
) -> None:
    body = org_header_update_gql(req)
    log.debug(body)
    tdjson = __auth_gql(body, headers)
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))


def org_footer_update_gql(req: OrgFooterUpdateRequest) -> GQLQueryBody:
    variables = {"imgPath": req.imgPath, "imgIdx": req.imgIdx}
    if req.orgId:
        variables["orgId"] = req.orgId
    return {
        "query": """mutation OrgFooterUpdate($orgId: ID, $imgPath: String!, $imgIdx: Int!) {
          api {
            orgFooterUpdate(orgId: $orgId, imgPath: $imgPath, imgIdx: $imgIdx)
          }
        }""",
        "variables": variables,
    }


def org_footer_update(
    req: OrgFooterUpdateRequest, headers: Dict[str, str] = {}
) -> None:
    body = org_footer_update_gql(req)
    log.debug(body)
    tdjson = __auth_gql(body, headers)

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


def import_task_create_gql(
    req: ImportTaskGQLRequest, headers: Dict[str, str] = {}
) -> None:
    body = import_task_create_gql_query(req)
    tdjson = __auth_gql(body, headers)

    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))


def import_task_update_gql_query(req: ImportTaskUpdateGQLRequest) -> GQLQueryBody:
    variables = {}
    variables["mentor"] = req.mentor
    if req.graphql_update:
        variables["graphQLUpdate"] = req.graphql_update
    if req.s3_video_migration:
        variables["s3VideoMigrateUpdate"] = req.s3_video_migration
    if req.migration_errors:
        variables["migrationErrors"] = req.migration_errors
    return {
        "query": """mutation ImportTaskUpdate($mentor: ID!, $graphQLUpdate: GraphQLUpdateInputType, $s3VideoMigrateUpdate: S3VideoMigrationInputType, $migrationErrors: [String]){
  api{
      importTaskUpdate(mentor: $mentor, graphQLUpdate: $graphQLUpdate, s3VideoMigrateUpdate: $s3VideoMigrateUpdate, migrationErrors: $migrationErrors)
  }
}""",
        "variables": variables,
    }


@dataclass
class ImportMentorGQLRequest:
    mentor: str
    json: MentorExportJson
    replacedMentorDataChanges: ReplacedMentorDataChanges


import_mentor_gql_response_schema = {
    "type": "object",
    "properties": {
        "data": {
            "type": "object",
            "properties": {
                "api": {
                    "type": "object",
                    "properties": {
                        "mentorImport": {
                            "type": "object",
                            "properties": {
                                "answers": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "hasUntransferredMedia": {
                                                "type": ["boolean", "null"]
                                            },
                                            "question": {
                                                "type": "object",
                                                "properties": {
                                                    "_id": {"type": "string"},
                                                },
                                                "required": ["_id"],
                                            },
                                            "externalVideoIds": {
                                                "type": "object",
                                                "properties": {
                                                    "wistiaId": {"type": "string"},
                                                },
                                            },
                                            "webMedia": {
                                                "type": ["object", "null"],
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "url": {"type": "string"},
                                                        "type": {"type": "string"},
                                                        "tag": {"type": "string"},
                                                        "needsTransfer": {
                                                            "type": "boolean"
                                                        },
                                                    },
                                                },
                                            },
                                            "mobileMedia": {
                                                "type": ["object", "null"],
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "url": {"type": "string"},
                                                        "type": {"type": "string"},
                                                        "tag": {"type": "string"},
                                                        "needsTransfer": {
                                                            "type": "boolean"
                                                        },
                                                    },
                                                },
                                            },
                                            "vttMedia": {
                                                "type": ["object", "null"],
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "url": {"type": "string"},
                                                        "type": {"type": "string"},
                                                        "tag": {"type": "string"},
                                                        "needsTransfer": {
                                                            "type": "boolean"
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                        "required": [
                                            "hasUntransferredMedia",
                                            "question",
                                            "webMedia",
                                            "mobileMedia",
                                            "vttMedia",
                                        ],
                                    },
                                }
                            },
                            "required": ["answers"],
                        }
                    },
                    "required": ["mentorImport"],
                }
            },
            "required": ["api"],
        }
    },
    "required": ["data"],
}


def import_mentor_gql_query(req: ImportMentorGQLRequest) -> GQLQueryBody:
    return {
        "query": """mutation MentorImport($mentor: ID!,$json:MentorImportJsonType!, $replacedMentorDataChanges: ReplacedMentorDataChangesType!){
            api{
                mentorImport(mentor: $mentor,json:$json, replacedMentorDataChanges: $replacedMentorDataChanges){
                    answers{
                        hasUntransferredMedia
                        externalVideoIds{
                            wistiaId
                        }
                        question{
                            _id
                        }
                        webMedia{
                            url
                            type
                            tag
                            needsTransfer
                        }
                        mobileMedia{
                            url
                            type
                            tag
                            needsTransfer
                        }
                        vttMedia{
                            url
                            type
                            tag
                            needsTransfer
                        }
                    }
                }
            }
            }""",
        "variables": {
            "mentor": req.mentor,
            "json": req.json,
            "replacedMentorDataChanges": req.replacedMentorDataChanges,
        },
    }


def import_task_update_gql(
    req: ImportTaskGQLRequest, headers: Dict[str, str] = {}
) -> None:
    body = import_task_update_gql_query(req)
    tdjson = __auth_gql(body, headers)

    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))


@dataclass
class UpdateAnswer:
    questionId: str
    web_media: Media = None
    mobile_media: Media = None
    vtt_media: Media = None
    transcript: str = None
    has_edited_transcript: bool = None


@dataclass
class UpdateAnswersGQLRequest:
    mentorId: str
    answers: List[UpdateAnswer]


def update_answers_gql_query(req: UpdateAnswersGQLRequest) -> GQLQueryBody:
    answers = list(
        map(
            lambda answer: {
                **(
                    {"mobileMedia": answer["mobile_media"]}
                    if "mobile_media" in answer
                    else {}
                ),
                **({"webMedia": answer["web_media"]} if "web_media" in answer else {}),
                **({"vttMedia": answer["vtt_media"]} if "vtt_media" in answer else {}),
                **(
                    {"hasEditedTranscript": answer["has_edited_transcript"]}
                    if "has_edited_transcript" in answer
                    else {}
                ),
                **(
                    {"transcript": answer["transcript"]}
                    if "transcript" in answer
                    else {}
                ),
                **(
                    {"questionId": answer["questionId"]}
                    if "questionId" in answer
                    else {}
                ),
            },
            req.answers,
        )
    )
    return {
        "query": """mutation UpdateAnswers($mentorId: ID!, $answers: [UploadAnswersType]) {
            api {
                updateAnswers(mentorId: $mentorId, answers: $answers)
            }
        }""",
        "variables": {
            "mentorId": req.mentorId,
            "answers": answers,
        },
    }


def update_answers_gql(
    req: UpdateAnswersGQLRequest, headers: Dict[str, str] = {}
) -> None:
    body = update_answers_gql_query(req)
    tdjson = __auth_gql(body, headers)

    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))


def media_update_gql(req: MediaUpdateRequest) -> GQLQueryBody:
    variables = {"mentorId": req.mentor, "questionId": req.question}
    if req.web_media:
        variables["webMedia"] = req.web_media
    if req.mobile_media:
        variables["mobileMedia"] = req.mobile_media
    if req.vtt_media:
        variables["vttMedia"] = req.vtt_media

    return {
        "query": """mutation MediaUpdate($mentorId: ID!, $questionId: ID!, $webMedia: AnswerMediaInputType, $mobileMedia: AnswerMediaInputType, $vttMedia: AnswerMediaInputType) {
            api {
                mediaUpdate(mentorId: $mentorId, questionId: $questionId, webMedia: $webMedia, mobileMedia: $mobileMedia, vttMedia: $vttMedia)
            }
        }""",
        "variables": variables,
    }


def validate_json(json_data, json_schema):
    try:
        jsonschema.validate(instance=json_data, schema=json_schema)
    except jsonschema.exceptions.ValidationError as err:
        log.error(msg=err)
        raise Exception(err)


def exec_graphql_with_json_validation(
    request_query, json_schema, headers: Dict[str, str]
):
    tdjson = __auth_gql(request_query, headers)
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))
    validate_json(tdjson, json_schema)
    return tdjson


class MentorImportMediaResponse:
    url: str
    type: str
    tag: str
    needsTransfer: bool


class MentorImportQuestionResponse:
    _id: str


class MentorImportAnswersResponse:
    hasUntransferredMedia: bool
    question: MentorImportQuestionResponse
    media: List[MentorImportMediaResponse]


class MentorImportGQLResponse:
    answers: List[MentorImportAnswersResponse]


def get_media_list_from_answer_gql(answer_gql):
    media_list = []
    if answer_gql["webMedia"]:
        media_list.append(answer_gql["webMedia"])
    if answer_gql["mobileMedia"]:
        media_list.append(answer_gql["mobileMedia"])
    if answer_gql["vttMedia"]:
        media_list.append(answer_gql["vttMedia"])
    return media_list


def import_mentor_gql(
    req: ImportMentorGQLRequest, headers: Dict[str, str] = {}
) -> MentorImportGQLResponse:
    query = import_mentor_gql_query(req)
    res = exec_graphql_with_json_validation(
        query, import_mentor_gql_response_schema, headers=headers
    )
    res_data = res["data"]["api"]["mentorImport"]
    import_response_data = {
        "answers": list(
            map(
                lambda answer: {
                    **answer,
                    "media": get_media_list_from_answer_gql(answer),
                },
                res_data["answers"],
            )
        )
    }
    return import_response_data


@dataclass
class UploadTaskRequest:
    mentor: str
    question: str
    trim_upload_task: TaskInfo
    transcode_web_task: TaskInfo
    transcode_mobile_task: TaskInfo
    transcribe_task: TaskInfo
    transcript: str = None
    original_media: Media = None


def upload_answer_update_gql(answer_req: AnswerUpdateRequest) -> GQLQueryBody:
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

    return {
        "query": """mutation UpdateUploadAnswerAndTaskStatus($mentorId: ID!, $questionId: ID!, $answer: UploadAnswerType!) {
            api {
                uploadAnswer(mentorId: $mentorId, questionId: $questionId, answer: $answer)
            }
        }""",
        "variables": variables,
    }


def upload_answer_update(
    answer_req: AnswerUpdateRequest, headers: Dict[str, str] = {}
) -> None:
    body = upload_answer_update_gql(answer_req)
    tdjson = __auth_gql(body, headers)

    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))


def upload_answer_and_task_req_gql(
    answer_req: AnswerUpdateRequest, task_req: UploadTaskRequest
) -> GQLQueryBody:
    variables = {}
    variables["mentorId"] = answer_req.mentor
    variables["questionId"] = answer_req.question

    variables["answer"] = {}
    if answer_req.transcript:
        variables["answer"]["transcript"] = answer_req.transcript
    if answer_req.has_edited_transcript is not None:
        variables["answer"]["hasEditedTranscript"] = answer_req.has_edited_transcript

    variables["status"] = {
        "transcodeWebTask": task_req.transcode_web_task,
        "transcodeMobileTask": task_req.transcode_mobile_task,
        "transcribeTask": task_req.transcribe_task,
        "trimUploadTask": task_req.trim_upload_task,
    }
    if task_req.transcript:
        variables["status"]["transcript"] = task_req.transcript
    return {
        "query": """mutation UpdateUploadAnswerAndTaskStatus($mentorId: ID!, $questionId: ID!, $answer: UploadAnswerType!, $status: UploadTaskInputType!) {
            api {
                uploadAnswer(mentorId: $mentorId, questionId: $questionId, answer: $answer)
                uploadTaskUpdate(mentorId: $mentorId, questionId: $questionId, status: $status)
            }
        }""",
        "variables": variables,
    }


def upload_answer_and_task_update(
    answer_req: AnswerUpdateRequest,
    task_req: UploadTaskRequest,
    headers: Dict[str, str] = {},
) -> None:
    body = upload_answer_and_task_req_gql(answer_req, task_req)
    tdjson = __auth_gql(body, headers)
    if "errors" in tdjson:
        raise Exception(json.dumps(tdjson.get("errors")))


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


def fetch_answer_transcript_and_media(
    mentor: str, question: str, headers: Dict[str, str] = {}
):
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
