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

class TestDetailResponse(BaseModel):
    id: int
    title: str
    description: str | None
    time_limit: int | None
    shuffle_questions: bool
    questions: list[dict]

class TestListResponse(BaseModel):
    tests: list[TestResponse]

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), request: Request = None):
    request_id = request.state.request_id if request else 'unknown'
    logger.debug(f"Decoding JWT token: {credentials.credentials[:10]}...", extra={'request_id': request_id})
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=['HS256'])
        return payload['sub']
    except jwt.ExpiredSignatureError:
        logger.error(f"JWT token expired", extra={'request_id': request_id})
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT token: {str(e)}", extra={'request_id': request_id})
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Unexpected error in JWT decoding: {str(e)}", extra={'request_id': request_id}, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@tests_router.get("/tests", summary="Retrieve list of tests", response_model=TestListResponse)
async def get_tests(request: Request, cursor=Depends(get_db), user_id: int = Depends(get_current_user)):
    request_id = request.state.request_id
    logger.debug(f"Fetching tests for user_id={user_id}", extra={'request_id': request_id})
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
                logger.info('No tests found', extra={'request_id': request_id})
                return {"tests": []}
            test_list = [
                TestResponse(
                    id=test['id'],
                    title=test['title'],
                    description=test['description'],
                    question_count=test['question_count']
                ) for test in tests
            ]
            logger.info(f"Retrieved {len(test_list)} tests for user_id={user_id}", extra={'request_id': request_id})
            return {"tests": test_list}
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise await handle_db_error(e, request_id)
        except Exception as e:
            logger.error(f"Unexpected error retrieving tests: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

@tests_router.get("/tests/{id}", summary="Retrieve test details", response_model=TestDetailResponse)
async def get_test(id: int, request: Request, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    request_id = request.state.request_id
    lang = get_language(request)
    logger.debug(f"Fetching test details: test_id={id}, user_id={user_id}", extra={'request_id': request_id})

    async with cursor:
        try:
            await check_creator_permission(cursor, user_id, test_id=id, lang=lang, request_id=request_id)
            await cursor.execute("SELECT id, title, description, time_limit, shuffle_questions FROM tests WHERE id = %s", (id,))
            test = await cursor.fetchone()
            if not test:
                logger.warning(f"Test not found: test_id={id}", extra={'request_id': request_id})
                raise HTTPException(status_code=404, detail=translate_message('test_not_found', lang))

            await cursor.execute("SELECT id, text, type, options, correct_answer FROM questions WHERE test_id = %s", (id,))
            questions = await cursor.fetchall()
            question_list = [
                {
                    "id": q['id'],
                    "text": q['text'],
                    "type": q['type'],
                    "options": json.loads(q['options']) if q['options'] else None,
                    "correct_answer": q['correct_answer']
                } for q in questions
            ]

            logger.info(f"Test details retrieved: test_id={id}, title={test['title']}, questions_count={len(questions)}", extra={'request_id': request_id})
            return TestDetailResponse(
                id=test['id'],
                title=test['title'],
                description=test['description'],
                time_limit=test['time_limit'],
                shuffle_questions=test['shuffle_questions'],
                questions=question_list
            )
        except HTTPException:
            raise
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise await handle_db_error(e, request_id)
        except Exception as e:
            logger.error(f"Unexpected error retrieving test: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

@tests_router.post("/tests", summary="Create a new test")
async def create_test(request: Request, data: TestRequest, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    request_id = request.state.request_id
    lang = get_language(request)
    logger.debug(f"Creating test: title={data.title}, user_id={user_id}, questions_count={len(data.questions)}", extra={'request_id': request_id})

    async with cursor:
        try:
            await check_creator_permission(cursor, user_id, lang=lang, request_id=request_id)
            await cursor.execute("SELECT id FROM tests WHERE title = %s", (data.title,))
            if await cursor.fetchone():
                logger.warning(f"Test title already exists: {data.title}", extra={'request_id': request_id})
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
                    logger.warning(f"Invalid options format for test_id={test_id}", extra={'request_id': request_id})
                    raise HTTPException(status_code=400, detail="Options must be a list of strings")
                await cursor.execute(
                    "INSERT INTO questions (test_id, text, type, options, correct_answer) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (test_id, q['text'], q['type'], json.dumps(options) if options else None, q.get('correct_answer'))
                )
            await cursor.connection.commit()
            logger.info(f"Test created: test_id={test_id}, title={data.title}, creator_id={user_id}", extra={'request_id': request_id})
            return {'test_id': test_id, 'message': translate_message('test_created', lang)}
        except HTTPException:
            raise
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise await handle_db_error(e, request_id)
        except Exception as e:
            logger.error(f"Unexpected error creating test: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

@tests_router.put("/tests/{id}", summary="Update an existing test")
async def update_test(id: int, request: Request, data: TestRequest, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    request_id = request.state.request_id
    lang = get_language(request)
    logger.debug(f"Updating test: test_id={id}, user_id={user_id}, title={data.title}, questions_count={len(data.questions)}", extra={'request_id': request_id})

    async with cursor:
        try:
            await check_creator_permission(cursor, user_id, test_id=id, lang=lang, request_id=request_id)
            await cursor.execute("SELECT id FROM tests WHERE title = %s AND id != %s", (data.title, id))
            if await cursor.fetchone():
                logger.warning(f"Test title already exists: {data.title}", extra={'request_id': request_id})
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
                    logger.warning(f"Invalid options format for test_id={id}", extra={'request_id': request_id})
                    raise HTTPException(status_code=400, detail="Options must be a list of strings")
                await cursor.execute(
                    "INSERT INTO questions (test_id, text, type, options, correct_answer) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (id, q['text'], q['type'], json.dumps(options) if options else None, q.get('correct_answer'))
                )
            await cursor.connection.commit()
            logger.info(f"Test updated: test_id={id}, title={data.title}", extra={'request_id': request_id})
            return {'message': translate_message('test_updated', lang)}
        except HTTPException:
            raise
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise await handle_db_error(e, request_id)
        except Exception as e:
            logger.error(f"Unexpected error updating test: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

@tests_router.delete("/tests/{id}", summary="Delete a test")
async def delete_test(id: int, request: Request, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    request_id = request.state.request_id
    lang = get_language(request)
    logger.debug(f"Deleting test: test_id={id}, user_id={user_id}", extra={'request_id': request_id})

    async with cursor:
        try:
            await check_creator_permission(cursor, user_id, test_id=id, lang=lang, request_id=request_id)
            await cursor.execute("DELETE FROM tests WHERE id = %s", (id,))
            await cursor.connection.commit()
            logger.info(f"Test deleted: test_id={id}", extra={'request_id': request_id})
            return {'message': translate_message('test_deleted', lang)}
        except HTTPException:
            raise
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise await handle_db_error(e, request_id)
        except Exception as e:
            logger.error(f"Unexpected error deleting test: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")