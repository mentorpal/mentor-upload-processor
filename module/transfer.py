import logging
import urllib.request
from os import remove

from .api import (
    ImportMentorGQLRequest,
    import_mentor_gql,
    update_media,
    MediaUpdateRequest,
    import_task_update_gql,
    ImportTaskUpdateGQLRequest,
)
from typing import List, TypedDict


class Media:
    type: str
    tag: str
    url: str
    needsTransfer: bool


class ProcessTransferRequest(TypedDict):
    mentor: str
    question: str


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


class Answer:
    _id: str
    question: Question
    hasEditedTranscript: bool
    transcript: str
    status: str
    media: List[Media]


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


def process_transfer_mentor(s3_client, s3_bucket, req: ProcessTransferMentor):
    mentor = req.get("mentor")
    mentor_export_json = req.get("mentorExportJson")
    replaced_mentor_data_changes = req.get("replacedMentorDataChanges")
    graphql_update = {"status": "IN_PROGRESS"}
    mentor_import_res = import_mentor(
        mentor, mentor_export_json, replaced_mentor_data_changes, graphql_update
    )

    answers = mentor_import_res["answers"]
    answers_with_media_transfers = list(
        filter(
            lambda a: len(a["media"] or []) > 0,
            answers,
        )
    )
    answer_media_migrations = [
        {"question": q["_id"], "status": "QUEUED"}
        for q in list(map(lambda a: a["question"], answers_with_media_transfers))
    ]
    s3_video_migration = {
        "status": "IN_PROGRESS",
        "answerMediaMigrations": answer_media_migrations,
    }
    import_task_update_gql(
        ImportTaskUpdateGQLRequest(mentor=mentor, s3_video_migration=s3_video_migration)
    )
    answer_failure = None
    for answer in answers_with_media_transfers:
        try:
            question = answer["question"]["_id"]
            for m in answer["media"]:
                if m.get("needsTransfer", False):
                    typ = m.get("type", "")
                    tag = m.get("tag", "")
                    root_ext = "vtt" if typ == "subtitles" else "mp4"
                    try:
                        file_path, headers = urllib.request.urlretrieve(
                            m.get("url", "")
                        )
                        item_path = f"videos/{mentor}/{question}/{tag}.{root_ext}"
                        content_type = "text/vtt" if typ == "subtitles" else "video/mp4"
                        s3_client.upload_file(
                            file_path,
                            s3_bucket,
                            item_path,
                            ExtraArgs={"ContentType": content_type},
                        )
                        m["needsTransfer"] = False
                        m["url"] = item_path
                        update_media_vars = {"mentor": mentor, "question": question}
                        if tag == "en":
                            update_media_vars["vtt_media"] = m
                        if tag == "web":
                            update_media_vars["web_media"] = m
                        if tag == "mobile":
                            update_media_vars["mobile_media"] = m
                        update_media(MediaUpdateRequest(**update_media_vars))
                        answer_media_migrate_update = {
                            "question": question,
                            "status": "DONE",
                        }
                        import_task_update_gql(
                            ImportTaskUpdateGQLRequest(
                                mentor=mentor,
                                answerMediaMigrateUpdate=answer_media_migrate_update,
                            )
                        )

                    except Exception as x:
                        media_url = m.get("url", "")
                        logging.error(f"Failed to upload video {media_url} to s3 {x}")
                        logging.exception(x)
                        raise x
                    finally:
                        try:
                            remove(file_path)
                        except:  # noqa: E722
                            pass  # lambdas tmp files are not important
                else:
                    answer_media_migrate_update = {
                        "question": question,
                        "status": "DONE",
                    }
                    import_task_update_gql(
                        ImportTaskUpdateGQLRequest(
                            mentor=mentor,
                            answerMediaMigrateUpdate=answer_media_migrate_update,
                        )
                    )
        except Exception as e:
            logging.error(
                f"Failed to process media for answer with question {question}"
            )
            answer_failure = e
            logging.exception(e)
            import_task_update_gql(
                ImportTaskUpdateGQLRequest(
                    mentor=mentor,
                    answerMediaMigrateUpdate={
                        "question": question,
                        "status": "FAILED",
                        "errorMessage": str(e),
                    },
                )
            )
    if answer_failure:
        raise Exception(f"Failed to transfer {mentor}")


def import_mentor(
    mentor, mentor_export_json, replaced_mentor_data_changes, graphql_update
):
    import_task_update_gql(
        ImportTaskUpdateGQLRequest(mentor=mentor, graphql_update=graphql_update)
    )
    try:
        mentor_import_res = import_mentor_gql(
            ImportMentorGQLRequest(
                mentor, mentor_export_json, replaced_mentor_data_changes
            )
        )
    except Exception as e:
        logging.error("Failed to import mentor")
        logging.error(e)
        import_task_update_gql(
            ImportTaskUpdateGQLRequest(
                mentor=mentor, graphql_update={"status": "FAILED"}
            )
        )
        raise e
    graphql_update = {"status": "DONE"}
    import_task_update_gql(
        ImportTaskUpdateGQLRequest(mentor=mentor, graphql_update=graphql_update)
    )

    return mentor_import_res
