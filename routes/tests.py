from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
import aiomysql
import json
import logging
from db import get_db
from utils import get_language, translate_message, handle_db_error, check_creator_permission
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os
from dotenv import load_dotenv

load_dotenv()
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is not set")

tests_router = APIRouter()
logger = logging.getLogger('app.tests')
security = HTTPBearer()

class TestRequest(BaseModel):
    title: str
    description: str | None = None
    time_limit: int | None = None
    shuffle_questions: bool = False
    questions: list[dict]

class TestResponse(BaseModel):
    id: int
    title: str
    description: str | None
    question_count: int

class TestListResponse(BaseModel):
    tests: list[TestResponse]

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=['HS256'])
        return payload['sub']
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@tests_router.get("/tests", summary="Retrieve list of tests", response_model=TestListResponse)
async def get_tests(request: Request, cursor=Depends(get_db), user_id: int = Depends(get_current_user)):
    logger.info(f'Fetching tests for user ID={user_id}')
    async with cursor:
        try:
            await cursor.execute("""
                SELECT t.id, t.title, t.description, COUNT(q.id) as question_count
                FROM tests t
                LEFT JOIN questions q ON t.id = q.test_id
                GROUP BY t.id, t.title, t.description
            """)
            tests = await cursor.fetchall()
            if not tests:
                logger.info('No tests found')
                return {"tests": []}
            test_list = [
                TestResponse(
                    id=test['id'],
                    title=test['title'],
                    description=test['description'],
                    question_count=test['question_count']
                ) for test in tests
            ]
            logger.info(f'Retrieved {len(test_list)} tests for user ID={user_id}')
            return {"tests": test_list}
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise handle_db_error(e)

@tests_router.post("/tests", summary="Create a new test")
async def create_test(request: Request, data: TestRequest, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    lang = get_language(request)
    logger.info(f'Create test attempt by user ID={user_id}')

    async with cursor:
        try:
            await check_creator_permission(cursor, user_id, lang=lang)
            await cursor.execute("SELECT id FROM tests WHERE title = %s", (data.title,))
            if await cursor.fetchone():
                raise HTTPException(status_code=400, detail=translate_message('validation_error', lang))

            await cursor.execute(
                "INSERT INTO tests (title, description, creator_id, time_limit, shuffle_questions) "
                "VALUES (%s, %s, %s, %s, %s)",
                (data.title, data.description, user_id, data.time_limit, data.shuffle_questions)
            )
            test_id = cursor.lastrowid

            for q in data.questions:
                options = q.get('options')
                if options and not all(isinstance(opt, str) for opt in options):
                    raise HTTPException(status_code=400, detail="Options must be a list of strings")
                await cursor.execute(
                    "INSERT INTO questions (test_id, text, type, options, correct_answer) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (test_id, q['text'], q['type'], json.dumps(options) if options else None, q.get('correct_answer'))
                )
            await cursor.connection.commit()
            logger.info(f'Test created: ID={test_id}, Title={data.title}, Creator ID={user_id}')
            return {'test_id': test_id, 'message': translate_message('test_created', lang)}
        except (aiomysql.IntegrityError, aiomysql.OperationalError) as e:
            raise handle_db_error(e)

@tests_router.put("/tests/{id}", summary="Update an existing test")
async def update_test(id: int, request: Request, data: TestRequest, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    lang = get_language(request)
    logger.info(f'Update test attempt for test ID={id} by user ID={user_id}')

    async with cursor:
        try:
            await check_creator_permission(cursor, user_id, test_id=id, lang=lang)
            await cursor.execute("SELECT id FROM tests WHERE title = %s AND id != %s", (data.title, id))
            if await cursor.fetchone():
                raise HTTPException(status_code=400, detail=translate_message('validation_error', lang))

            await cursor.execute(
                "UPDATE tests SET title = %s, description = %s, time_limit = %s, shuffle_questions = %s "
                "WHERE id = %s",
                (data.title, data.description, data.time_limit, data.shuffle_questions, id)
            )
            await cursor.execute("DELETE FROM questions WHERE test_id = %s", (id,))

            for q in data.questions:
                options = q.get('options')
                if options and not all(isinstance(opt, str) for opt in options):
                    raise HTTPException(status_code=400, detail="Options must be a list of strings")
                await cursor.execute(
                    "INSERT INTO questions (test_id, text, type, options, correct_answer) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (id, q['text'], q['type'], json.dumps(options) if options else None, q.get('correct_answer'))
                )
            await cursor.connection.commit()
            logger.info(f'Test updated: ID={id}, Title={data.title}')
            return {'message': translate_message('test_updated', lang)}
        except (aiomysql.IntegrityError, aiomysql.OperationalError) as e:
            raise handle_db_error(e)

@tests_router.delete("/tests/{id}", summary="Delete a test")
async def delete_test(id: int, request: Request, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    lang = get_language(request)
    logger.info(f'Delete test attempt for test ID={id} by user ID={user_id}')

    async with cursor:
        try:
            await check_creator_permission(cursor, user_id, test_id=id, lang=lang)
            await cursor.execute("DELETE FROM tests WHERE id = %s", (id,))
            await cursor.connection.commit()
            logger.info(f'Test deleted: ID={id}')
            return {'message': translate_message('test_deleted', lang)}
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise handle_db_error(e)