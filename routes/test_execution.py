from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import db_config
import pymysql
import json
import random
import datetime
import csv
from io import StringIO
from utils import get_language, translate_message
import logging

test_execution_bp = Blueprint('test_execution', __name__)
logger = logging.getLogger('app.test_execution')

@test_execution_bp.route('/tests/<int:id>/start', methods=['POST'])
@jwt_required()
def start_test(id):
    user_id = get_jwt_identity()
    lang = get_language()
    logger.info(f'Start test attempt for test ID={id} by user ID={user_id}')

    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user or user['role'] != 'participant':
                logger.warning(f'No permission: User ID={user_id} is not a participant')
                return jsonify({'message': translate_message('no_permission', lang)}), 403

            cursor.execute("SELECT id FROM tests WHERE id = %s", (id,))
            if not cursor.fetchone():
                logger.warning(f'Test not found: ID={id}')
                return jsonify({'message': translate_message('test_not_found', lang)}), 404

            cursor.execute("SELECT id FROM test_attempts WHERE user_id = %s AND test_id = %s", (user_id, id))
            if cursor.fetchone():
                logger.warning(f'No permission: User ID={user_id} already attempted test ID={id}')
                return jsonify({'message': translate_message('no_permission', lang)}), 403

            cursor.execute(
                "INSERT INTO test_attempts (user_id, test_id) VALUES (%s, %s)",
                (user_id, id)
            )
            attempt_id = conn.insert_id()

            cursor.execute("SELECT shuffle_questions FROM tests WHERE id = %s", (id,))
            shuffle = cursor.fetchone()['shuffle_questions']

            cursor.execute("SELECT id, text, type, options FROM questions WHERE test_id = %s", (id,))
            questions = cursor.fetchall()

            if shuffle:
                random.shuffle(questions)
                logger.info(f'Questions shuffled for test ID={id}')

            for q in questions:
                q['options'] = json.loads(q['options']) if q['options'] else None

            conn.commit()
            logger.info(f'Test started: ID={id}, Attempt ID={attempt_id}, User ID={user_id}')
            return jsonify({
                'test_id': id,
                'questions': [
                    {
                        'id': q['id'],
                        'text': q['text'],
                        'type': q['type'],
                        'options': q['options']
                    } for q in questions
                ]
            }), 200
    except Exception as e:
        logger.error(f'Error starting test ID={id}: {e}')
        return jsonify({'message': translate_message('validation_error', lang)}), 500
    finally:
        conn.close()

@test_execution_bp.route('/tests/<int:id>/submit', methods=['POST'])
@jwt_required()
def submit_test(id):
    user_id = get_jwt_identity()
    lang = get_language()
    logger.info(f'Submit test attempt for test ID={id} by user ID={user_id}')

    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user or user['role'] != 'participant':
                logger.warning(f'No permission: User ID={user_id} is not a participant')
                return jsonify({'message': translate_message('no_permission', lang)}), 403

            cursor.execute("SELECT id FROM tests WHERE id = %s", (id,))
            if not cursor.fetchone():
                logger.warning(f'Test not found: ID={id}')
                return jsonify({'message': translate_message('test_not_found', lang)}), 404

            cursor.execute("SELECT id FROM test_attempts WHERE user_id = %s AND test_id = %s AND end_time IS NULL", (user_id, id))
            attempt = cursor.fetchone()
            if not attempt:
                logger.warning(f'No permission: No active attempt for user ID={user_id}, test ID={id}')
                return jsonify({'message': translate_message('no_permission', lang)}), 403

            data = request.get_json()
            if not data or not data.get('answers'):
                logger.warning('Validation error: Missing answers')
                return jsonify({'message': translate_message('validation_error', lang)}), 400

            cursor.execute("SELECT COUNT(*) as count FROM questions WHERE test_id = %s", (id,))
            total_questions = cursor.fetchone()['count']

            score = 0
            correct_answers = []

            for ans in data['answers']:
                cursor.execute("SELECT correct_answer, test_id FROM questions WHERE id = %s", (ans['question_id'],))
                question = cursor.fetchone()
                if not question or question['test_id'] != id:
                    conn.rollback()
                    logger.warning(f'Validation error: Invalid question ID={ans["question_id"]} for test ID={id}')
                    return jsonify({'message': translate_message('validation_error', lang)}), 400

                is_correct = (ans['answer'] == question['correct_answer'])
                if is_correct:
                    score += 1

                cursor.execute(
                    "INSERT INTO answers (attempt_id, question_id, answer, is_correct, answer_time) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        attempt['id'],
                        ans['question_id'],
                        ans['answer'],
                        is_correct,
                        ans.get('answer_time', 0)
                    )
                )
                correct_answers.append({
                    'question_id': ans['question_id'],
                    'correct_answer': question['correct_answer']
                })

            final_score = (score / total_questions) * 100 if total_questions > 0 else 0
            cursor.execute(
                "UPDATE test_attempts SET score = %s, end_time = %s WHERE id = %s",
                (final_score, datetime.datetime.utcnow(), attempt['id'])
            )
            conn.commit()
            logger.info(f'Test submitted: ID={id}, Attempt ID={attempt["id"]}, User ID={user_id}, Score={final_score}')
            return jsonify({
                'score': final_score,
                'correct_answers': correct_answers
            }), 200
    except Exception as e:
        logger.error(f'Error submitting test ID={id}: {e}')
        return jsonify({'message': translate_message('validation_error', lang)}), 500
    finally:
        conn.close()

@test_execution_bp.route('/tests/<int:id>/stats', methods=['GET'])
@jwt_required()
def get_test_stats(id):
    user_id = get_jwt_identity()
    lang = get_language()
    logger.info(f'Retrieve stats for test ID={id} by user ID={user_id}')

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

            cursor.execute("SELECT AVG(score) as avg_score FROM test_attempts WHERE test_id = %s", (id,))
            avg_score = cursor.fetchone()['avg_score'] or 0

            cursor.execute(
                "SELECT AVG(TIMESTAMPDIFF(SECOND, start_time, end_time)) as avg_time "
                "FROM test_attempts WHERE test_id = %s AND end_time IS NOT NULL",
                (id,)
            )
            avg_completion_time = cursor.fetchone()['avg_time'] or 0

            cursor.execute("SELECT id FROM questions WHERE test_id = %s", (id,))
            questions = cursor.fetchall()
            difficulty = {}
            for q in questions:
                cursor.execute(
                    "SELECT COUNT(*) as total, SUM(is_correct) as correct, AVG(answer_time) as avg_time "
                    "FROM answers WHERE question_id = %s",
                    (q['id'],)
                )
                stats = cursor.fetchone()
                if stats['total'] > 0:
                    difficulty[f"question_{q['id']}"] = {
                        'correct_percentage': (stats['correct'] / stats['total']) * 100,
                        'average_time': stats['avg_time'] or 0
                    }

            logger.info(f'Stats retrieved for test ID={id}: Avg Score={avg_score}, Avg Time={avg_completion_time}')
            return jsonify({
                'average_score': round(avg_score, 1),
                'completion_time': round(avg_completion_time, 1),
                'difficulty': difficulty
            }), 200
    except Exception as e:
        logger.error(f'Error retrieving stats for test ID={id}: {e}')
        return jsonify({'message': translate_message('validation_error', lang)}), 500
    finally:
        conn.close()

@test_execution_bp.route('/tests/<int:id>/stats/export', methods=['GET'])
@jwt_required()
def export_stats(id):
    user_id = get_jwt_identity()
    lang = get_language()
    logger.info(f'Export stats for test ID={id} by user ID={user_id}')

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

            cursor.execute(
                "SELECT user_id, score, start_time, end_time, "
                "TIMESTAMPDIFF(SECOND, start_time, end_time) as completion_time "
                "FROM test_attempts WHERE test_id = %s",
                (id,)
            )
            attempts = cursor.fetchall()

            si = StringIO()
            writer = csv.writer(si)
            writer.writerow(['User ID', 'Score', 'Start Time', 'End Time', 'Completion Time (s)'])

            for attempt in attempts:
                writer.writerow([
                    attempt['user_id'],
                    attempt['score'],
                    attempt['start_time'],
                    attempt['end_time'],
                    attempt['completion_time'] or 0
                ])

            logger.info(f'Stats exported for test ID={id}')
            response = make_response(si.getvalue())
            response.headers['Content-Disposition'] = f'attachment; filename=test_{id}_stats.csv'
            response.headers['Content-Type'] = 'text/csv'
            return response
    except Exception as e:
        logger.error(f'Error exporting stats for test ID={id}: {e}')
        return jsonify({'message': translate_message('validation_error', lang)}), 500
    finally:
        conn.close()