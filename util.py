#
# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
#
import os
import logging
from api import fetch_task


def require_env(n: str) -> str:
    env_val = os.environ.get(n, "")
    if not env_val:
        raise EnvironmentError(f"missing required env var {n}")
    return env_val


s3_bucket = require_env("S3_STATIC_ARN").split(":")[-1]
logging.info("using s3 bucket %s", s3_bucket)


def load_sentry():
    if os.environ.get("IS_SENTRY_ENABLED", "") == "true":
        logging.info("SENTRY enabled, calling init")
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
        logging.error("task it doesnt match %s %s", task_id, upload_task["taskList"])
        raise Exception(
            "task it doesnt match %s %s",
            task_id,
            [t["task_id"] for t in upload_task["taskList"]],
        )
    return stored_task
