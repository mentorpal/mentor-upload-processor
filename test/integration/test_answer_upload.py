import requests
import pytest
import json
from .util import get_auth_headers, api_endpoint
from urllib3 import encode_multipart_formdata
import time

mentor_jwt_id = "6196af5e068d43dc686194ed"  # milan, todo: create a test mentor
test_mentor = "6196af5e068d43dc686194f8"  # milan, todo: create a test mentor
test_question = "61499cfba8bc83d04ac1675d"  # 6149a443a8bc83b2eac16f46
headers = get_auth_headers(mentor_jwt_id, [test_mentor])


def remove_task_status(mentorId, questionId, headers):
    gql = {
        "variables": {"mentorId": mentorId, "questionId": questionId},
        "query": """
        mutation UploadTaskDelete($questionId: ID!, $mentorId: ID) {
          me {
            uploadTaskDelete(questionId: $questionId, mentorId: $mentorId)
          }
        }
        """,
    }
    response = requests.post(
        "https://api.qamentorpal.org/graphql/graphql",  # TODO
        headers=headers,
        data=json.dumps(gql),
    )
    # if this query fails, we might have to manually clean up the task status
    if response.status_code != 200 or "errors" in response.text:
        print(
            "failed to remove task status, might have to do it manually",
            response.status_code,
            response.text,
        )
        pytest.fail(reason="failed to remove task status, might have to do it manually")


def test_successful_upload():
    # first upload video to the presigned bucket:
    response = requests.get(f"{api_endpoint}/upload/url", headers=headers)
    print(response.status_code, response.text)
    assert response.status_code == 200
    presigned = json.loads(response.text)["data"]
    fields = {}
    for key, value in presigned["fields"].items():
        fields[key] = value
    with open("test/integration/fixtures/celery-short.mp4", "rb") as f:
        # fields["file"] = ("celery-short.mp4", img_data.getvalue(), "video/mp4")"),
        fields["file"] = f.read()
    body, content_type = encode_multipart_formdata(fields)
    response = requests.post(
        presigned["url"],
        headers={"Content-Type": content_type},
        data=body,
    )
    print(response.status_code, response.text)
    assert response.status_code == 204

    # now call the answer upload endpoint with the newly uploaded video:
    headers["Content-Type"] = "application/json"
    response = requests.post(
        f"{api_endpoint}/upload/answer",
        headers=headers,
        data=json.dumps(
            {
                "mentor": test_mentor,
                "question": test_question,
                "video": presigned["fields"]["key"],
                "trim": {"start": 5, "end": 12},
                "hasEditedTranscript": False,
            }
        ),
    )

    print(response.status_code, response.text)
    assert response.status_code == 200
    assert "taskList" in response.text
    #  wait until processing is completed
    gql = {
        "variables": {"mentorId": test_mentor},
        "query": """
            query FetchUploadTasks($mentorId: ID) {
            me {
                uploadTasks(mentorId: $mentorId) {
                question {
                    _id
                    question
                }
                trimUploadTask{
                    task_name
                    status
                }
                transcodeWebTask{
                    task_name
                    status
                }
                transcodeMobileTask{
                    task_name
                    status
                }
                transcribeTask{
                    task_name
                    status
                }
                }
            }
            }
        """,
    }

    headers["Content-Type"] = "application/json"
    while True:
        response = requests.post(
            "https://api.qamentorpal.org/graphql/graphql",  # TODO
            headers=headers,
            data=json.dumps(gql),
        )
        assert response.status_code == 200
        assert "errors" not in response.text

        tasks = json.loads(response.text)["data"]
        task = tasks["me"]["uploadTasks"][0]
        task_names = (
            "trimUploadTask",
            "transcodeWebTask",
            "transcodeMobileTask",
            "transcribeTask",
        )
        statuses = [task[name]["status"] for name in task_names]
        if any([status == "FAILED" for status in statuses]):
            remove_task_status(test_mentor, test_question, headers)
            print(tasks)
            pytest.fail(reason="task failed")
        if all([status == "DONE" for status in statuses]):
            remove_task_status(test_mentor, test_question, headers)
            break
        time.sleep(1)
