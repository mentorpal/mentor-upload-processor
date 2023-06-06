# This software is Copyright ©️ 2020 The University of Southern California. All Rights Reserved.
# Permission to use, copy, modify, and distribute this software and its documentation for educational, research and non-profit purposes, without fee, and without a written agreement is hereby granted, provided that the above copyright notice and subject to the full license file found in the root of this software deliverable. Permission to make commercial use of this software may be obtained by contacting:  USC Stevens Center for Innovation University of Southern California 1150 S. Olive Street, Suite 2300, Los Angeles, CA 90115, USA Email: accounting@stevens.usc.edu
#
# The full terms of this copyright and license should always be found in the root directory of this software deliverable as "license.txt" and if these terms are not found with this software, please contact the USC Stevens Center for the full license.
transfer_mentor_json_schema = {
    "type": "object",
    "properties": {
        "mentor": {"type": "string"},
        "mentorExportJson": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "mentorInfo": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "firstName": {"type": "string"},
                        "title": {"type": "string"},
                        "email": {"type": "string"},
                        "thumbnail": {"type": "string"},
                        "allowContact": {"type": ["boolean", "null"]},
                        "defaultSubject": {"type": ["string", "null"]},
                        "mentorType": {"type": "string"},
                    },
                },
                "subjects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "_id": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "type": {"type": "string"},
                            "isRequired": {"type": "boolean"},
                            "categories": {
                                "type": "array",
                                "items": {"$ref": "#/$defs/Category"},
                            },
                            "topics": {
                                "type": "array",
                                "items": {"$ref": "#/$defs/Topic"},
                            },
                            "questions": {
                                "type": "array",
                                "items": {"$ref": "#/$defs/SubjectQuestionGQL"},
                            },
                        },
                    },
                },
                "questions": {"type": "array", "items": {"$ref": "#/$defs/Question"}},
                "answers": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/AnswerGQL"},
                },
                "userQuestions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "_id": {"type": "string"},
                            "question": {"type": "string"},
                            "confidence": {"type": "number"},
                            "classifierAnswerType": {"type": "string"},
                            "feedback": {"type": "string"},
                            "mentor": {
                                "type": "object",
                                "properties": {
                                    "_id": {"type": "string"},
                                    "name": {"type": "string"},
                                },
                            },
                            "classifierAnswer": {
                                "type": "object",
                                "properties": {
                                    "_id": {"type": "string"},
                                    "question": {
                                        "type": "object",
                                        "properties": {
                                            "_id": {"type": "string"},
                                            "question": {"type": "string"},
                                        },
                                    },
                                    "transcript": {"type": "string"},
                                },
                            },
                            "graderAnswer": {
                                "type": ["object", "null"],
                                "properties": {
                                    "_id": {"type": "string"},
                                    "question": {
                                        "type": "object",
                                        "properties": {
                                            "_id": {"type": "string"},
                                            "question": {"type": "string"},
                                        },
                                    },
                                    "transcript": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
            "required": [
                "id",
                "mentorInfo",
                "subjects",
                "questions",
                "answers",
                "userQuestions",
            ],
        },
        "replacedMentorDataChanges": {
            "type": "object",
            "properties": {
                "questionChanges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "editType": {"type": "string"},
                            "data": {"$ref": "#/$defs/Question"},
                        },
                    },
                },
                "answerChanges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "editType": {"type": "string"},
                            "data": {"$ref": "#/$defs/AnswerGQL"},
                        },
                    },
                },
            },
            "required": ["questionChanges", "answerChanges"],
        },
    },
    "required": ["mentor", "mentorExportJson", "replacedMentorDataChanges"],
    "$defs": {
        "Category": {
            "type": ["object", "null"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
            },
        },
        "Topic": {
            "type": ["object", "null"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
            },
        },
        "Question": {
            "type": "object",
            "properties": {
                "_id": {"type": "string"},
                "question": {"type": "string"},
                "type": {"type": "string"},
                "name": {"type": "string"},
                "clientId": {"type": "string"},
                "paraphrases": {"type": "array", "items": {"type": "string"}},
                "mentor": {"type": ["string", "null"]},
                "mentorType": {"type": ["string", "null"]},
                "minVideoLength": {"type": ["number", "null"]},
            },
        },
        "SubjectQuestionGQL": {
            "type": "object",
            "properties": {
                "question": {"$ref": "#/$defs/Question"},
                "category": {"$ref": "#/$defs/Category"},
                "topics": {"type": "array", "items": {"$ref": "#/$defs/Topic"}},
            },
        },
        "ExternalVideoIdsGQL": {
            "type": "object",
            "properties": {"wistiaId": {"type": "string"}},
        },
        "AnswerGQL": {
            "type": "object",
            "properties": {
                "_id": {"type": "string"},
                "question": {"$ref": "#/$defs/Question"},
                "hasEditedTranscript": {"type": "boolean"},
                "transcript": {"type": "string"},
                "status": {"type": "string"},
                "externalVideoIds": {"$ref": "#/$defs/ExternalVideoIdsGQL"},
                "webMedia": {
                    "type": ["object", "null"],
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "tag": {"type": "string"},
                            "url": {"type": "string"},
                            "needsTransfer": {"type": "boolean"},
                        },
                    },
                },
                "mobileMedia": {
                    "type": ["object", "null"],
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "tag": {"type": "string"},
                            "url": {"type": "string"},
                            "needsTransfer": {"type": "boolean"},
                        },
                    },
                },
                "vttMedia": {
                    "type": ["object", "null"],
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "tag": {"type": "string"},
                            "url": {"type": "string"},
                            "needsTransfer": {"type": "boolean"},
                        },
                    },
                },
                "hasUntransferredMedia": {"type": ["boolean", "null"]},
            },
        },
    },
    "additionalProperties": False,
}
