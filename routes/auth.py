from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from db import db_config
import pymysql
from utils import get_language, translate_message
import logging

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger('app.auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    lang = get_language()
    logger.info(f'Register attempt for email: {data.get("email", "unknown")}')

    if not data or not data.get('email') or not data.get('password') or not data.get('role'):
        logger.warning('Validation error: Missing required fields')
        return jsonify({'message': translate_message('validation_error', lang)}), 400

    if data['role'] not in ['participant', 'creator']:
        logger.warning(f'Validation error: Invalid role {data["role"]}')
        return jsonify({'message': translate_message('validation_error', lang)}), 400

    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE email = %s", (data['email'],))
            if cursor.fetchone():
                logger.warning(f'Validation error: Email {data["email"]} already exists')
                return jsonify({'message': translate_message('validation_error', lang)}), 400

            password_hash = generate_password_hash(data['password'], method='bcrypt')
            cursor.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s)",
                (data['email'], password_hash, data['role'])
            )
            user_id = conn.insert_id()
            conn.commit()
            logger.info(f'User registered: ID={user_id}, Email={data["email"]}, Role={data["role"]}')
        return jsonify({
            'message': translate_message('user_registered', lang),
            'user_id': user_id
        }), 201
    except Exception as e:
        logger.error(f'Error during registration: {e}')
        return jsonify({'message': translate_message('validation_error', lang)}), 500
    finally:
        conn.close()

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    lang = get_language()
    logger.info(f'Login attempt for email: {data.get("email", "unknown")}')

    if not data or not data.get('email') or not data.get('password'):
        logger.warning('Validation error: Missing required fields')
        return jsonify({'message': translate_message('validation_error', lang)}), 400

    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, password_hash FROM users WHERE email = %s", (data['email'],))
            user = cursor.fetchone()
            if not user or not check_password_hash(user['password_hash'], data['password']):
                logger.warning(f'Invalid credentials for email: {data["email"]}')
                return jsonify({'message': translate_message('invalid_credentials', lang)}), 401

            access_token = create_access_token(identity=user['id'])
            logger.info(f'User logged in: ID={user["id"]}, Email={data["email"]}')
            return jsonify({'access_token': access_token}), 200
    except Exception as e:
        logger.error(f'Error during login: {e}')
        return jsonify({'message': translate_message('validation_error', lang)}), 500
    finally:
        conn.close()