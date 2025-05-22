from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import db_config
import pymysql
import json
from utils import get_language, translate_message
import logging

tests_bp = Blueprint('tests', __name__)
logger = logging.getLogger('app.tests')

@tests_bp.route('/tests', methods=['POST'])
@jwt_required()
def create_test():
    user_id = get_jwt_identity()
    lang = get_language()
    logger.info(f'Create test attempt by user ID={user_id}')

    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user or user['role'] != 'creator':
                logger.warning(f'No permission: User ID={user_id} is not a creator')
                return jsonify({'message': translate_message('no_permission', lang)}), 403

        data = request.get_json()
        if not data or not data.get('title') or not data.get('questions'):
            logger.warning('Validation error: Missing required fields')
            return jsonify({'message': translate_message('validation_error', lang)}), 400

        cursor.execute(
            "INSERT INTO tests (title, description, creator_id, time_limit, shuffle_questions) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                data['title'],
                data.get('description'),
                user_id,
                data.get('time_limit'),
                data.get('shuffle_questions', False)
            )
        )
        test_id = conn.insert_id()

        for q in data['questions']:
            if q['type'] == 'multiple_choice' and (len(q.get('options', [])) < 2 or len(q.get('options', [])) > 5):
                conn.rollback()
                logger.warning(f'Validation error: Invalid options for question in test ID={test_id}')
                return jsonify({'message': translate_message('validation_error', lang)}), 400
            cursor.execute(
                "INSERT INTO questions (test_id, text, type, options, correct_answer) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    test_id,
                    q['text'],
                    q['type'],
                    json.dumps(q.get('options')),
                    q.get('correct_answer')
                )
            )
        conn.commit()
        logger.info(f'Test created: ID={test_id}, Title={data["title"]}, Creator ID={user_id}')
        return jsonify({
            'test_id': test_id,
            'message': translate_message('test_created', lang)
        }), 201
    except Exception as e:
        logger.error(f'Error creating test: {e}')
        return jsonify({'message': translate_message('validation_error', lang)}), 500
    finally:
        conn.close()

@tests_bp.route('/tests/<int:id>', methods=['PUT'])
@jwt_required()
def update_test(id):
    user_id = get_jwt_identity()
    lang = get_language()
    logger.info(f'Update test attempt for test ID={id} by user ID={user_id}')

    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user or user['role'] != 'creator':
                logger.warning(f'No permission: User ID={user_id} is not a creator')
                return jsonify({'message': translate_message('no_permission', lang)}), 403

            cursor.execute("SELECT creator_id FROM tests WHERE id = %s", (id,))
            test = cursor.fetchone()
            if not test or test['creator_id'] != user_id:
                logger.warning(f'Test not found or not owned by user ID={user_id}, Test ID={id}')
                return jsonify({'message': translate_message('test_not_found', lang)}), 404

        data = request.get_json()
        if not data or not data.get('title') or not data.get('questions'):
            logger.warning('Validation error: Missing required fields')
            return jsonify({'message': translate_message('validation_error', lang)}), 400

        cursor.execute(
            "UPDATE tests SET title = %s, description = %s, time_limit = %s, shuffle_questions = %s "
            "WHERE id = %s",
            (
                data['title'],
                data.get('description'),
                data.get('time_limit'),
                data.get('shuffle_questions', False),
                id
            )
        )

        cursor.execute("DELETE FROM questions WHERE test_id = %s", (id,))

        for q in data['questions']:
            if q['type'] == 'multiple_choice' and (len(q.get('options', [])) < 2 or len(q.get('options', [])) > 5):
                conn.rollback()
                logger.warning(f'Validation error: Invalid options for question in test ID={id}')
                return jsonify({'message': translate_message('validation_error', lang)}), 400
            cursor.execute(
                "INSERT INTO questions (test_id, text, type, options, correct_answer) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    id,
                    q['text'],
                    q['type'],
                    json.dumps(q.get('options')),
                    q.get('correct_answer')
                )
            )

        conn.commit()
        logger.info(f'Test updated: ID={id}, Title={data["title"]}')
        return jsonify({'message': translate_message('test_updated', lang)}), 200
    except Exception as e:
        logger.error(f'Error updating test ID={id}: {e}')
        return jsonify({'message': translate_message('validation_error', lang)}), 500
    finally:
        conn.close()

@tests_bp.route('/tests/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_test(id):
    user_id = get_jwt_identity()
    lang = get_language()
    logger.info(f'Delete test attempt for test ID={id} by user ID={user_id}')

    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user or user['role'] != 'creator':
                logger.warning(f'No permission: User ID={user_id} is not a creator')
                return jsonify({'message': translate_message('no_permission', lang)}), 403

            cursor.execute("SELECT creator_id FROM tests WHERE id = %s", (id,))
            test = cursor.fetchone()
            if not test or test['creator_id'] != user_id:
                logger.warning(f'Test not found or not owned by user ID={user_id}, Test ID={id}')
                return jsonify({'message': translate_message('test_not_found', lang)}), 404

            cursor.execute("DELETE FROM tests WHERE id = %s", (id,))
            conn.commit()
            logger.info(f'Test deleted: ID={id}')
        return jsonify({'message': translate_message('test_deleted', lang)}), 200
    except Exception as e:
        logger.error(f'Error deleting test ID={id}: {e}')
        return jsonify({'message': translate_message('validation_error', lang)}), 500
    finally:
        conn.close()