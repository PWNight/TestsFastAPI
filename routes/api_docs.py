from flask import Blueprint, jsonify
from utils import get_language, translate_message
import logging

api_docs_bp = Blueprint('api_docs', __name__)
logger = logging.getLogger('app.api_docs')

@api_docs_bp.route('/api', methods=['GET'])
def api_docs():
    lang = get_language()
    logger.info(f'API documentation requested, language: {lang}')
    try:
        response = jsonify({
            'message': translate_message('api_documentation', lang),
            'endpoints': [
                {
                    'path': '/api/auth/register',
                    'method': 'POST',
                    'description': translate_message('register_user', lang),
                    'authentication': 'None',
                    'request_body': {
                        'email': 'string (required, valid email address)',
                        'password': 'string (required, minimum length 6)',
                        'role': 'string (required, either "participant" or "creator")'
                    },
                    'responses': {
                        '201': {
                            'description': translate_message('user_registered', lang),
                            'content': {
                                'message': 'string',
                                'user_id': 'integer'
                            }
                        },
                        '400': {
                            'description': translate_message('validation_error', lang),
                            'content': {
                                'message': 'string'
                            }
                        }
                    }
                },
                {
                    'path': '/api/auth/login',
                    'method': 'POST',
                    'description': translate_message('login_user', lang),
                    'authentication': 'None',
                    'request_body': {
                        'email': 'string (required, valid email address)',
                        'password': 'string (required)'
                    },
                    'responses': {
                        '200': {
                            'description': 'Successful login',
                            'content': {
                                'access_token': 'string (JWT token)'
                            }
                        },
                        '400': {
                            'description': translate_message('validation_error', lang),
                            'content': {
                                'message': 'string'
                            }
                        },
                        '401': {
                            'description': translate_message('invalid_credentials', lang),
                            'content': {
                                'message': 'string'
                            }
                        }
                    }
                },
                {
                    'path': '/api/tests',
                    'method': 'POST',
                    'description': translate_message('create_test', lang),
                    'authentication': 'JWT (creator role required)',
                    'request_body': {
                        'title': 'string (required)',
                        'description': 'string (optional)',
                        'time_limit': 'integer (optional, in seconds)',
                        'shuffle_questions': 'boolean (optional, default: false)',
                        'questions': 'array of objects (required, each containing: text (string), type (string: "open" or "multiple_choice"), options (array of strings, required for multiple_choice), correct_answer (string))'
                    },
                    'responses': {
                        '201': {
                            'description': translate_message('test_created', lang),
                            'content': {
                                'test_id': 'integer',
                                'message': 'string'
                            }
                        },
                        '400': {
                            'description': translate_message('validation_error', lang),
                            'content': {
                                'message': 'string'
                            }
                        },
                        '403': {
                            'description': translate_message('no_permission', lang),
                            'content': {
                                'message': 'string'
                            }
                        }
                    }
                },
                {
                    'path': '/api/tests/<id>',
                    'method': 'PUT',
                    'description': translate_message('update_test', lang),
                    'authentication': 'JWT (creator role required, must be test owner)',
                    'path_params': {
                        'id': 'integer (test ID)'
                    },
                    'request_body': {
                        'title': 'string (required)',
                        'description': 'string (optional)',
                        'time_limit': 'integer (optional, in seconds)',
                        'shuffle_questions': 'boolean (optional, default: false)',
                        'questions': 'array of objects (required, each containing: text (string), type (string: "open" or "multiple_choice"), options (array of strings, required for multiple_choice), correct_answer (string))'
                    },
                    'responses': {
                        '200': {
                            'description': translate_message('test_updated', lang),
                            'content': {
                                'message': 'string'
                            }
                        },
                        '400': {
                            'description': translate_message('validation_error', lang),
                            'content': {
                                'message': 'string'
                            }
                        },
                        '403': {
                            'description': translate_message('no_permission', lang),
                            'content': {
                                'message': 'string'
                            }
                        },
                        '404': {
                            'description': translate_message('test_not_found', lang),
                            'content': {
                                'message': 'string'
                            }
                        }
                    }
                },
                {
                    'path': '/api/tests/<id>',
                    'method': 'DELETE',
                    'description': translate_message('delete_test', lang),
                    'authentication': 'JWT (creator role required, must be test owner)',
                    'path_params': {
                        'id': 'integer (test ID)'
                    },
                    'request_body': None,
                    'responses': {
                        '200': {
                            'description': translate_message('test_deleted', lang),
                            'content': {
                                'message': 'string'
                            }
                        },
                        '403': {
                            'description': translate_message('no_permission', lang),
                            'content': {
                                'message': 'string'
                            }
                        },
                        '404': {
                            'description': translate_message('test_not_found', lang),
                            'content': {
                                'message': 'string'
                            }
                        }
                    }
                },
                {
                    'path': '/api/tests/<id>/start',
                    'method': 'POST',
                    'description': translate_message('start_test', lang),
                    'authentication': 'JWT (participant role required)',
                    'path_params': {
                        'id': 'integer (test ID)'
                    },
                    'request_body': None,
                    'responses': {
                        '200': {
                            'description': 'Test started, questions returned',
                            'content': {
                                'test_id': 'integer',
                                'questions': 'array of objects (each containing: id (integer), text (string), type (string), options (array of strings or null))'
                            }
                        },
                        '403': {
                            'description': translate_message('no_permission', lang),
                            'content': {
                                'message': 'string'
                            }
                        },
                        '404': {
                            'description': translate_message('test_not_found', lang),
                            'content': {
                                'message': 'string'
                            }
                        }
                    }
                },
                {
                    'path': '/api/tests/<id>/submit',
                    'method': 'POST',
                    'description': translate_message('submit_test', lang),
                    'authentication': 'JWT (participant role required)',
                    'path_params': {
                        'id': 'integer (test ID)'
                    },
                    'request_body': {
                        'answers': 'array of objects (required, each containing: question_id (integer), answer (string), answer_time (float, optional))'
                    },
                    'responses': {
                        '200': {
                            'description': 'Test submitted, score calculated',
                            'content': {
                                'score': 'float (percentage)',
                                'correct_answers': 'array of objects (each containing: question_id (integer), correct_answer (string))'
                            }
                        },
                        '400': {
                            'description': translate_message('validation_error', lang),
                            'content': {
                                'message': 'string'
                            }
                        },
                        '403': {
                            'description': translate_message('no_permission', lang),
                            'content': {
                                'message': 'string'
                            }
                        },
                        '404': {
                            'description': translate_message('test_not_found', lang),
                            'content': {
                                'message': 'string'
                            }
                        }
                    }
                },
                {
                    'path': '/api/tests/<id>/stats',
                    'method': 'GET',
                    'description': translate_message('get_test_stats', lang),
                    'authentication': 'JWT (creator role required, must be test owner)',
                    'path_params': {
                        'id': 'integer (test ID)'
                    },
                    'request_body': None,
                    'responses': {
                        '200': {
                            'description': 'Test statistics',
                            'content': {
                                'average_score': 'float',
                                'completion_time': 'float (seconds)',
                                'difficulty': 'object (keys are question IDs, values are objects with correct_percentage (float) and average_time (float))'
                            }
                        },
                        '403': {
                            'description': translate_message('no_permission', lang),
                            'content': {
                                'message': 'string'
                            }
                        },
                        '404': {
                            'description': translate_message('test_not_found', lang),
                            'content': {
                                'message': 'string'
                            }
                        }
                    }
                },
                {
                    'path': '/api/tests/<id>/stats/export',
                    'method': 'GET',
                    'description': translate_message('export_test_stats', lang),
                    'authentication': 'JWT (creator role required, must be test owner)',
                    'path_params': {
                        'id': 'integer (test ID)'
                    },
                    'request_body': None,
                    'responses': {
                        '200': {
                            'description': 'CSV file with test attempt statistics',
                            'content': 'CSV file (columns: User ID, Score, Start Time, End Time, Completion Time (s))'
                        },
                        '403': {
                            'description': translate_message('no_permission', lang),
                            'content': {
                                'message': 'string'
                            }
                        },
                        '404': {
                            'description': translate_message('test_not_found', lang),
                            'content': {
                                'message': 'string'
                            }
                        }
                    }
                }
            ]
        })
        logger.info('API documentation served successfully')
        return response, 200
    except Exception as e:
        logger.error(f'Error serving API documentation: {e}')
        return jsonify({'message': translate_message('validation_error', lang)}), 500