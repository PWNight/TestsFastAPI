from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
import aiomysql
import bcrypt
import jwt
import logging
from db import get_db
from utils import get_language, translate_message, handle_db_error
from datetime import datetime, timedelta
import os
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
JWT_EXP_HOURS = int(os.getenv('JWT_EXP_HOURS', 24))
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is not set")

auth_router = APIRouter()
logger = logging.getLogger('app.auth')
security = HTTPBearer()

class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    role: str

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), request: Request = None):
    request_id = getattr(request.state, 'request_id', 'unknown')
    logger.debug(f"Decoding JWT token: {credentials.credentials[:10]}...", extra={'request_id': request_id})
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=['HS256'])
        user_id = payload['sub']
        logger.info(f"Decoded JWT for user ID={user_id}", extra={'request_id': request_id})
        return user_id
    except jwt.ExpiredSignatureError:
        logger.error(f"JWT token expired", extra={'request_id': request_id})
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT token: {str(e)}", extra={'request_id': request_id})
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Unexpected error in JWT decoding: {str(e)}", extra={'request_id': request_id}, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@auth_router.post("/register", summary="Register a new user")
async def register(request: Request, data: RegisterRequest, cursor=Depends(get_db)):
    request_id = getattr(request.state, 'request_id', 'unknown')
    lang = get_language(request)
    logger.debug(f"Register attempt: email={data.email}, role={data.role}", extra={'request_id': request_id})

    async with cursor:
        try:
            await cursor.execute("SELECT id FROM users WHERE email = %s", (data.email,))
            if await cursor.fetchone():
                logger.warning(f"Email already exists: {data.email}", extra={'request_id': request_id})
                raise HTTPException(status_code=400, detail=translate_message('validation_error', lang))

            password_hash = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await cursor.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s)",
                (data.email, password_hash, data.role)
            )
            user_id = cursor.lastrowid
            await cursor.connection.commit()
            logger.info(f"User registered: ID={user_id}, Email={data.email}, Role={data.role}", extra={'request_id': request_id})
            # Проверка существования пользователя
            await cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not await cursor.fetchone():
                logger.error(f"User ID={user_id} not found after registration", extra={'request_id': request_id})
                raise HTTPException(status_code=500, detail="Failed to register user")
            return {'message': translate_message('user_registered', lang), 'user_id': user_id}
        except (aiomysql.IntegrityError, aiomysql.OperationalError) as e:
            raise await handle_db_error(e, request_id)
        except Exception as e:
            logger.error(f"Unexpected error during registration: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

@auth_router.post("/login", summary="Authenticate a user")
async def login(request: Request, data: LoginRequest, cursor=Depends(get_db)):
    request_id = getattr(request.state, 'request_id', 'unknown')
    lang = get_language(request)
    logger.debug(f"Login attempt: email={data.email}", extra={'request_id': request_id})

    async with cursor:
        try:
            await cursor.execute("SELECT id, password_hash, role FROM users WHERE email = %s", (data.email,))
            user = await cursor.fetchone()
            if not user or not bcrypt.checkpw(data.password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                logger.warning(f"Invalid credentials for email: {data.email}", extra={'request_id': request_id})
                raise HTTPException(status_code=401, detail=translate_message('invalid_credentials', lang))

            access_token = jwt.encode(
                {'sub': user['id'], 'exp': int((datetime.now() + timedelta(hours=JWT_EXP_HOURS)).timestamp())},
                JWT_SECRET_KEY, algorithm='HS256'
            )
            logger.info(f"User logged in: ID={user['id']}, Email={data.email}", extra={'request_id': request_id})
            return {'access_token': access_token}
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise await handle_db_error(e, request_id)
        except Exception as e:
            logger.error(f"Unexpected error during login: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

@auth_router.get("/me", summary="Get current user details", response_model=UserResponse)
async def get_user_details(request: Request, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    request_id = getattr(request.state, 'request_id', 'unknown')
    lang = get_language(request)
    logger.debug(f"Fetching details for user ID={user_id}", extra={'request_id': request_id})

    async with cursor:
        try:
            await cursor.execute("SELECT id, email, role FROM users WHERE id = %s", (user_id,))
            user = await cursor.fetchone()
            if not user:
                logger.warning(f"User not found: ID={user_id}", extra={'request_id': request_id})
                raise HTTPException(status_code=404, detail=translate_message('user_not_found', lang))
            logger.info(f"User details retrieved: ID={user['id']}, Email={user['email']}, Role={user['role']}", extra={'request_id': request_id})
            return UserResponse(id=user['id'], email=user['email'], role=user['role'])
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise await handle_db_error(e, request_id)
        except Exception as e:
            logger.error(f"Unexpected error during user details retrieval: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")