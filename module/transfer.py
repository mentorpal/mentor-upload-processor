# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
from dataclasses import dataclass
import logging
import queue
from threading import Thread
import urllib.request
from os import remove

from .api import (
    ImportMentorGQLRequest,
    UpdateAnswersGQLRequest,
    import_mentor_gql,
    update_answers_gql,
    import_task_update_gql,
    ImportTaskUpdateGQLRequest,
)
from typing import Dict, List, TypedDict


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


@dataclass
class WorkerResult:
    update: Dict
    errors: List[str]


def thread_video_uploads(
    answer_list, mentor, s3_client, s3_bucket, no_workers
) -> List[WorkerResult]:
    class Worker(Thread):
        def __init__(self, request_queue):
            Thread.__init__(self)
            self.queue = request_queue
            self.results = []

        def run(self):
            while True:
                answer = self.queue.get()
                if answer == "":
                    break

                update, errors = transfer_mentor_videos_in_parellel(
                    answer, mentor, s3_client, s3_bucket
                )

                self.results.append(WorkerResult(update, errors))
                self.queue.task_done()

    # Create queue and add req params
    q = queue.Queue()
    for r in answer_list:
        q.put(r)

    # Workers keep working till they receive an empty string
    for _ in range(no_workers):
        q.put("")

    # Create workers and add to the queue
    workers = []
    for _ in range(no_workers):
        worker = Worker(q)
        worker.start()
        workers.append(worker)
    # Join workers to wait till they finished
    for worker in workers:
        worker.join()

    # Combine results from all workers
    r = []
    for worker in workers:
        r.extend(worker.results)

    return r


def transfer_mentor_videos_in_parellel(answer, mentor, s3_client, s3_bucket):
    updates_to_return = []
    errors_to_return = []
    try:
        question = answer["question"]["_id"]
        for m in answer["media"]:
            if m.get("needsTransfer", False):
                typ = m.get("type", "")
                tag = m.get("tag", "")
                root_ext = "vtt" if typ == "subtitles" else "mp4"
                try:
                    file_path, headers = urllib.request.urlretrieve(m.get("url", ""))
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
                    update_media_vars = {"questionId": question}
                    if tag == "en":
                        update_media_vars["vtt_media"] = m
                    if tag == "web":
                        update_media_vars["web_media"] = m
                    if tag == "mobile":
                        update_media_vars["mobile_media"] = m
                    updates_to_return.append(update_media_vars)
                except Exception as x:
                    media_url = m.get("url", "")
                    errors_to_return.append(
                        f"Failed to upload video {media_url} to s3 {x}"
                    )
                    logging.exception(x)
                finally:
                    try:
                        remove(file_path)
                    except:  # noqa: E722
                        pass  # lambdas tmp files are not important
        return updates_to_return, errors_to_return
    except Exception as e:
        logging.error(f"Failed to process media for answer with question {question}")
        logging.exception(e)
    finally:
        logging.error(f"another video DONE for {mentor}")


def process_transfer_mentor(
    s3_client, s3_bucket, req: ProcessTransferMentor, auth_headers
):
    mentor = req.get("mentor")
    mentor_export_json = req.get("mentorExportJson")
    replaced_mentor_data_changes = req.get("replacedMentorDataChanges")
    graphql_update = {"status": "IN_PROGRESS"}
    mentor_import_res = import_mentor(
        mentor,
        mentor_export_json,
        replaced_mentor_data_changes,
        graphql_update,
        auth_headers,
    )

    answers = mentor_import_res["answers"]
    answers_with_media_transfers = list(
        filter(
            lambda a: len(a["media"] or []) > 0,
            answers,
        )
    )
    s3_video_migration = {"status": "IN_PROGRESS"}
    import_task_update_gql(
        ImportTaskUpdateGQLRequest(
            mentor=mentor, s3_video_migration=s3_video_migration
        ),
        auth_headers,
    )

    answer_args_results = thread_video_uploads(
        answers_with_media_transfers, mentor, s3_client, s3_bucket, 12
    )
    answer_updates_unflat = list(map(lambda r: r.update, answer_args_results))
    answer_updates = [item for sublist in answer_updates_unflat for item in sublist]
    errors_unflat = list(map(lambda r: r.errors, answer_args_results))
    errors = [item for sublist in errors_unflat for item in sublist]
    chunks = [answer_updates[x: x + 100] for x in range(0, len(answer_updates), 100)]
    for answer_chunk in chunks:
        update_answers_gql(
            UpdateAnswersGQLRequest(mentorId=mentor, answers=answer_chunk), auth_headers
        )

    s3_video_migration_update = {"status": "DONE"}
    import_task_update_gql(
        ImportTaskUpdateGQLRequest(
            mentor=mentor,
            s3_video_migration=s3_video_migration_update,
            migration_errors=errors,
        ),
        auth_headers,
    )


def import_mentor(
    mentor,
    mentor_export_json,
    replaced_mentor_data_changes,
    graphql_update,
    auth_headers,
):
    import_task_update_gql(
        ImportTaskUpdateGQLRequest(mentor=mentor, graphql_update=graphql_update),
        auth_headers,
    )
    try:
        mentor_import_res = import_mentor_gql(
            ImportMentorGQLRequest(
                mentor, mentor_export_json, replaced_mentor_data_changes
            ),
            auth_headers,
        )
    except Exception as e:
        logging.error("Failed to import mentor")
        logging.error(e)
        import_task_update_gql(
            ImportTaskUpdateGQLRequest(
                mentor=mentor, graphql_update={"status": "FAILED"}
            ),
            auth_headers,
        )
        raise e
    graphql_update = {"status": "DONE"}
    import_task_update_gql(
        ImportTaskUpdateGQLRequest(mentor=mentor, graphql_update=graphql_update),
        auth_headers,
    )

    return mentor_import_res
