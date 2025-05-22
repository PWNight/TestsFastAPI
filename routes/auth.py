from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
import aiomysql
import bcrypt
import jwt
import logging
from db import db_config
from schemas import user_schema
from utils import get_language, translate_message
import os
from dotenv import load_dotenv

load_dotenv()
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')

auth_router = APIRouter()
logger = logging.getLogger('app.auth')

class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str

class LoginRequest(BaseModel):
    email: str
    password: str

async def get_db():
    pool = await aiomysql.create_pool(**db_config)
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            yield cursor
        conn.close()
    pool.close()
    await pool.wait_closed()

@auth_router.post("/register", summary="Register a new user")
async def register(request: Request, data: RegisterRequest, cursor=Depends(get_db)):
    lang = get_language(request)
    logger.info(f'Register attempt for email: {data.email}')

    try:
        validated_data = user_schema.load(data.dict())
    except Exception as e:
        logger.warning(f'Validation error: {e}')
        raise HTTPException(status_code=400, detail=translate_message('validation_error', lang))

    async with cursor:
        await cursor.execute("SELECT id FROM users WHERE email = %s", (data.email,))
        if await cursor.fetchone():
            logger.warning(f'Validation error: Email {data.email} already exists')
            raise HTTPException(status_code=400, detail=translate_message('validation_error', lang))

        password_hash = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        await cursor.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s)",
            (data.email, password_hash, data.role)
        )
        user_id = cursor._last_insert_id
        await cursor._connection.commit()
        logger.info(f'User registered: ID={user_id}, Email={data.email}, Role={data.role}')
        return {
            'message': translate_message('user_registered', lang),
            'user_id': user_id
        }

@auth_router.post("/login", summary="Authenticate a user")
async def login(request: Request, data: LoginRequest, cursor=Depends(get_db)):
    lang = get_language(request)
    logger.info(f'Login attempt for email: {data.email}')

    try:
        user_schema.load({'email': data.email, 'password': data.password})
    except Exception as e:
        logger.warning(f'Validation error: {e}')
        raise HTTPException(status_code=400, detail=translate_message('validation_error', lang))

    async with cursor:
        await cursor.execute("SELECT id, password_hash FROM users WHERE email = %s", (data.email,))
        user = await cursor.fetchone()
        if not user or not bcrypt.checkpw(data.password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            logger.warning(f'Invalid credentials for email: {data.email}')
            raise HTTPException(status_code=401, detail=translate_message('invalid_credentials', lang))

        access_token = jwt.encode({'sub': user['id'], 'exp': 3600 * 24}, JWT_SECRET_KEY, algorithm='HS256')
        logger.info(f'User logged in: ID={user["id"]}, Email={data.email}')
        return {'access_token': access_token}