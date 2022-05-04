# TODO: Most objects that could possibly be null here need to be fixed by updating GQL schema with a default value and then running an update script
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
        "AnswerGQL": {
            "type": "object",
            "properties": {
                "_id": {"type": "string"},
                "question": {"$ref": "#/$defs/Question"},
                "hasEditedTranscript": {"type": "boolean"},
                "transcript": {"type": "string"},
                "status": {"type": "string"},
                "media": {
                    "type": ["array", "null"],
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
                "hasUntransferredMedia": {"type": "boolean"},
            },
        },
    },
    "additionalProperties": False,
}
