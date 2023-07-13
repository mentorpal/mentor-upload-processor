# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
import re


def vtt_file_validation(file_path: str):
    with open(file_path, "r") as file:
        vtt_content = file.read()
        if not vtt_content.startswith("WEBVTT"):
            raise Exception(
                "Invalid VTT file format. Missing or incorrect header (WEBVTT)"
            )
        timestamp_pattern = re.compile(
            r"^\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}$", re.MULTILINE
        )
        timestamps = re.findall(timestamp_pattern, vtt_content)
        if not timestamps:
            raise Exception("Invalid VTT file structure. No timestamps found.")
        for timestamp in timestamps:
            if not is_valid_timestamp(timestamp):
                raise Exception(f"Invalid timestamp format: {timestamp}")


def is_valid_timestamp(timestamp):
    start_time, end_time = timestamp.split(" --> ")
    if not is_valid_time_format(start_time) or not is_valid_time_format(end_time):
        return False
    return True


def is_valid_time_format(time):
    time_format_pattern = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}$")
    return bool(re.match(time_format_pattern, time))
