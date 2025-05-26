from fastapi import APIRouter, HTTPException, Request, Depends, Response
from pydantic import BaseModel
import aiomysql
import json
import random
import datetime
import pandas as pd
from io import BytesIO
import logging
from db import get_db
from utils import get_language, translate_message, handle_db_error, check_creator_permission, check_participant_permission
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os
from dotenv import load_dotenv
from pandas.io.excel import ExcelWriter

load_dotenv()
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is not set")

test_execution_router = APIRouter()
logger = logging.getLogger('app.test_execution')
security = HTTPBearer()

class SubmitRequest(BaseModel):
    answers: list[dict]

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), request: Request = None):
    request_id = getattr(request.state, 'request_id', 'unknown')
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

@test_execution_router.post("/tests/{id}/start", summary="Start a test")
async def start_test(id: int, request: Request, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    request_id = getattr(request.state, 'request_id', 'unknown')
    lang = get_language(request)
    logger.debug(f"Starting test: test_id={id}, user_id={user_id}", extra={'request_id': request_id})

    async with cursor:
        try:
            await check_participant_permission(cursor, user_id, lang, request_id)
            await cursor.execute("SELECT id FROM tests WHERE id = %s", (id,))
            if not await cursor.fetchone():
                logger.warning(f"Test not found: test_id={id}", extra={'request_id': request_id})
                raise HTTPException(status_code=404, detail=translate_message('test_not_found', lang))

            await cursor.execute("SELECT id FROM test_attempts WHERE user_id = %s AND test_id = %s", (user_id, id))
            if await cursor.fetchone():
                logger.warning(f"Test already attempted: test_id={id}, user_id={user_id}", extra={'request_id': request_id})
                raise HTTPException(status_code=403, detail=translate_message('no_permission', lang))

            await cursor.execute("INSERT INTO test_attempts (user_id, test_id) VALUES (%s, %s)", (user_id, id))
            attempt_id = cursor.lastrowid

            await cursor.execute("SELECT shuffle_questions FROM tests WHERE id = %s", (id,))
            shuffle = (await cursor.fetchone())['shuffle_questions']

            await cursor.execute("SELECT id, text, type, options FROM questions WHERE test_id = %s", (id,))
            questions = await cursor.fetchall()
            if shuffle:
                random.shuffle(questions)

            for q in questions:
                q['options'] = json.loads(q['options']) if q['options'] else None

            await cursor.connection.commit()
            logger.info(f"Test started: test_id={id}, attempt_id={attempt_id}, user_id={user_id}", extra={'request_id': request_id})
            return {
                'test_id': id,
                'questions': [{'id': q['id'], 'text': q['text'], 'type': q['type'], 'options': q['options']} for q in questions]
            }
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise await handle_db_error(e, request_id)
        except Exception as e:
            logger.error(f"Unexpected error starting test: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

@test_execution_router.post("/tests/{id}/submit", summary="Submit test answers")
async def submit_test(id: int, request: Request, data: SubmitRequest, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    request_id = getattr(request.state, 'request_id', 'unknown')
    lang = get_language(request)
    logger.debug(f"Submitting test: test_id={id}, user_id={user_id}, answers_count={len(data.answers)}", extra={'request_id': request_id})

    if not data.answers:
        logger.warning(f"No answers provided for test_id={id}, user_id={user_id}", extra={'request_id': request_id})
        raise HTTPException(status_code=400, detail=translate_message('validation_error', lang))

    async with cursor:
        try:
            await check_participant_permission(cursor, user_id, lang, request_id)
            await cursor.execute("SELECT id FROM tests WHERE id = %s", (id,))
            if not await cursor.fetchone():
                logger.warning(f"Test not found: test_id={id}", extra={'request_id': request_id})
                raise HTTPException(status_code=404, detail=translate_message('test_not_found', lang))

            await cursor.execute("SELECT id FROM test_attempts WHERE user_id = %s AND test_id = %s AND end_time IS NULL", (user_id, id))
            attempt = await cursor.fetchone()
            if not attempt:
                logger.warning(f"No active attempt found: test_id={id}, user_id={user_id}", extra={'request_id': request_id})
                raise HTTPException(status_code=403, detail=translate_message('no_permission', lang))

            question_ids = [ans['question_id'] for ans in data.answers]
            await cursor.execute("SELECT id FROM questions WHERE test_id = %s AND id IN %s", (id, tuple(question_ids) if question_ids else (0,)))
            valid_question_ids = {q['id'] for q in await cursor.fetchall()}
            if set(question_ids) - valid_question_ids:
                logger.warning(f"Invalid question IDs provided: {set(question_ids) - valid_question_ids}", extra={'request_id': request_id})
                raise HTTPException(status_code=400, detail=translate_message('validation_error', lang))

            await cursor.execute("SELECT COUNT(*) as count FROM questions WHERE test_id = %s", (id,))
            total_questions = (await cursor.fetchone())['count']

            score = 0
            correct_answers = []
            for ans in data.answers:
                await cursor.execute("SELECT correct_answer, test_id FROM questions WHERE id = %s", (ans['question_id'],))
                question = await cursor.fetchone()
                if not question or question['test_id'] != id:
                    logger.warning(f"Invalid question: question_id={ans['question_id']}, test_id={id}", extra={'request_id': request_id})
                    raise HTTPException(status_code=400, detail=translate_message('validation_error', lang))

                is_correct = (ans['answer'] == question['correct_answer'])
                if is_correct:
                    score += 1

                await cursor.execute(
                    "INSERT INTO answers (attempt_id, question_id, answer, is_correct, answer_time) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (attempt['id'], ans['question_id'], ans['answer'], is_correct, ans.get('answer_time', 0))
                )
                correct_answers.append({'question_id': ans['question_id'], 'correct_answer': question['correct_answer']})

            final_score = (score / total_questions) * 100 if total_questions > 0 else 0
            await cursor.execute(
                "UPDATE test_attempts SET score = %s, end_time = %s WHERE id = %s",
                (final_score, datetime.datetime.now(datetime.UTC), attempt['id'])
            )
            await cursor.connection.commit()
            logger.info(f"Test submitted: test_id={id}, attempt_id={attempt['id']}, user_id={user_id}, score={final_score}", extra={'request_id': request_id})
            return {'score': final_score, 'correct_answers': correct_answers}
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise await handle_db_error(e, request_id)
        except Exception as e:
            logger.error(f"Unexpected error submitting test: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

@test_execution_router.get("/tests/{id}/stats", summary="Retrieve test statistics")
async def get_test_stats(id: int, request: Request, user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    request_id = getattr(request.state, 'request_id', 'unknown')
    lang = get_language(request)
    logger.debug(f"Retrieving stats: test_id={id}, user_id={user_id}", extra={'request_id': request_id})

    async with cursor:
        try:
            await check_creator_permission(cursor, user_id, test_id=id, lang=lang, request_id=request_id)
            await cursor.execute("SELECT AVG(score) as avg_score FROM test_attempts WHERE test_id = %s", (id,))
            avg_score = (await cursor.fetchone())['avg_score'] or 0

            await cursor.execute(
                "SELECT AVG(TIMESTAMPDIFF(SECOND, start_time, end_time)) as avg_time "
                "FROM test_attempts WHERE test_id = %s AND end_time IS NOT NULL",
                (id,)
            )
            avg_completion_time = (await cursor.fetchone())['avg_time'] or 0

            await cursor.execute("SELECT id FROM questions WHERE test_id = %s", (id,))
            questions = await cursor.fetchall()
            difficulty = {}
            for q in questions:
                await cursor.execute(
                    "SELECT COUNT(*) as total, SUM(is_correct) as correct, AVG(answer_time) as avg_time "
                    "FROM answers WHERE question_id = %s",
                    (q['id'],)
                )
                stats = await cursor.fetchone()
                if stats['total'] > 0:
                    difficulty[f"question_{q['id']}"] = {
                        'correct_percentage': (stats['correct'] / stats['total']) * 100,
                        'average_time': stats['avg_time'] or 0
                    }

            logger.info(f"Stats retrieved: test_id={id}, avg_score={avg_score}, avg_completion_time={avg_completion_time}", extra={'request_id': request_id})
            return {
                'average_score': round(avg_score, 1),
                'completion_time': round(avg_completion_time, 1),
                'difficulty': difficulty
            }
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise await handle_db_error(e, request_id)
        except Exception as e:
            logger.error(f"Unexpected error retrieving stats: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

@test_execution_router.get("/tests/{id}/stats/export", summary="Export test statistics")
async def export_stats(id: int, request: Request, format: str = "csv", user_id: int = Depends(get_current_user), cursor=Depends(get_db)):
    request_id = getattr(request.state, 'request_id', 'unknown')
    lang = get_language(request)
    logger.debug(f"Exporting stats: test_id={id}, user_id={user_id}, format={format}", extra={'request_id': request_id})

    if format not in ['csv', 'json', 'excel']:
        logger.warning(f"Invalid format requested: {format}", extra={'request_id': request_id})
        raise HTTPException(status_code=400, detail=translate_message('validation_error', lang))

    async with cursor:
        try:
            await check_creator_permission(cursor, user_id, test_id=id, lang=lang, request_id=request_id)
            await cursor.execute(
                "SELECT user_id, score, start_time, end_time, "
                "TIMESTAMPDIFF(SECOND, start_time, end_time) as completion_time "
                "FROM test_attempts WHERE test_id = %s",
                (id,)
            )
            attempts = await cursor.fetchall()

            data = [
                {
                    'User ID': attempt['user_id'],
                    'Score': attempt['score'],
                    'Start Time': attempt['start_time'],
                    'End Time': attempt['end_time'],
                    'Completion Time (s)': attempt['completion_time'] or 0
                } for attempt in attempts
            ]

            logger.info(f"Stats exported: test_id={id}, format={format}, records={len(data)}", extra={'request_id': request_id})
            if format == "json":
                return data
            elif format == "excel":
                df = pd.DataFrame(data)
                output = BytesIO()
                with ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                output.seek(0)
                return Response(
                    content=output.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=test_{id}_stats.xlsx"}
                )
            else:  # csv
                df = pd.DataFrame(data)
                return Response(
                    content=df.to_csv(index=False),
                    media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=test_{id}_stats.csv"}
                )
        except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
            raise await handle_db_error(e, request_id)
        except Exception as e:
            logger.error(f"Unexpected error exporting stats: {str(e)}", extra={'request_id': request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")