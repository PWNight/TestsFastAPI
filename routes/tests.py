from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
import aiomysql
import json
import logging
from db import db_config
from schemas import test_schema, question_schema
from utils import get_language, translate_message
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

tests_router = APIRouter()
logger = logging.getLogger('app.tests')
security = HTTPBearer()

class TestRequest(BaseModel):
    title: str
    description: str | None = None
    time_limit: int | None = None
    shuffle_questions: bool = False
    questions: list[dict]

async def get_db():
    pool = await aiomysql.create_pool(**db_config)
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            yield cursor
        conn.close()
    pool.close()
    await pool.wait_closed()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, os.getenv('JWT_SECRET_KEY'), algorithms=['HS256'])
        return payload['sub']
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@tests_router.post("/tests", summary="Create a new test")
async def create_test(request: Request, data: TestRequest, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    lang = get_language(request)
    logger.info(f'Create test attempt by user ID={user_id}')

    try:
        validated_test = test_schema.load(data.dict(exclude={'questions'}))
        validated_questions = question_schema.load(data.questions, many=True)
    except Exception as e:
        logger.warning(f'Validation error: {e}')
        raise HTTPException(status_code=400, detail=translate_message('validation_error', lang))

    async with cursor:
        await cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        user = await cursor.fetchone()
        if not user or user['role'] != 'creator':
            logger.warning(f'No permission: User ID={user_id} is not a creator')
            raise HTTPException(status_code=403, detail=translate_message('no_permission', lang))

        await cursor.execute(
            "INSERT INTO tests (title, description, creator_id, time_limit, shuffle_questions) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                data.title,
                data.description,
                user_id,
                data.time_limit,
                data.shuffle_questions
            )
        )
        test_id = cursor._last_insert_id

        for q in data.questions:
            await cursor.execute(
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
        await cursor._connection.commit()
        logger.info(f'Test created: ID={test_id}, Title={data.title}, Creator ID={user_id}')
        return {
            'test_id': test_id,
            'message': translate_message('test_created', lang)
        }

@tests_router.put("/tests/{id}", summary="Update an existing test")
async def update_test(id: int, request: Request, data: TestRequest, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    lang = get_language(request)
    logger.info(f'Update test attempt for test ID={id} by user ID={user_id}')

    try:
        validated_test = test_schema.load(data.dict(exclude={'questions'}))
        validated_questions = question_schema.load(data.questions, many=True)
    except Exception as e:
        logger.warning(f'Validation error: {e}')
        raise HTTPException(status_code=400, detail=translate_message('validation_error', lang))

    async with cursor:
        await cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        user = await cursor.fetchone()
        if not user or user['role'] != 'creator':
            logger.warning(f'No permission: User ID={user_id} is not a creator')
            raise HTTPException(status_code=403, detail=translate_message('no_permission', lang))

        await cursor.execute("SELECT creator_id FROM tests WHERE id = %s", (id,))
        test = await cursor.fetchone()
        if not test or test['creator_id'] != user_id:
            logger.warning(f'Test not found or not owned by user ID={user_id}, Test ID={id}')
            raise HTTPException(status_code=404, detail=translate_message('test_not_found', lang))

        await cursor.execute(
            "UPDATE tests SET title = %s, description = %s, time_limit = %s, shuffle_questions = %s "
            "WHERE id = %s",
            (
                data.title,
                data.description,
                data.time_limit,
                data.shuffle_questions,
                id
            )
        )

        await cursor.execute("DELETE FROM questions WHERE test_id = %s", (id,))

        for q in data.questions:
            await cursor.execute(
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

        await cursor._connection.commit()
        logger.info(f'Test updated: ID={id}, Title={data.title}')
        return {'message': translate_message('test_updated', lang)}

@tests_router.delete("/tests/{id}", summary="Delete a test")
async def delete_test(id: int, request: Request, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    lang = get_language(request)
    logger.info(f'Delete test attempt for test ID={id} by user ID={user_id}')

    async with cursor:
        await cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        user = await cursor.fetchone()
        if not user or user['role'] != 'creator':
            logger.warning(f'No permission: User ID={user_id} is not a creator')
            raise HTTPException(status_code=403, detail=translate_message('no_permission', lang))

        await cursor.execute("SELECT creator_id FROM tests WHERE id = %s", (id,))
        test = await cursor.fetchone()
        if not test or test['creator_id'] != user_id:
            logger.warning(f'Test not found or not owned by user ID={user_id}, Test ID={id}')
            raise HTTPException(status_code=404, detail=translate_message('test_not_found', lang))

        await cursor.execute("DELETE FROM tests WHERE id = %s", (id,))
        await cursor._connection.commit()
        logger.info(f'Test deleted: ID={id}')
        return {'message': translate_message('test_deleted', lang)}