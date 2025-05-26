from pydantic import BaseModel, EmailStr, field_validator
from fastapi import HTTPException
from typing import List, Optional
import logging

logger = logging.getLogger('app.schemas')

class UserSchema(BaseModel):
    email: EmailStr
    role: str
    password: str

    @field_validator('role')
    def validate_role(cls, value: str):
        logger.debug(f"Validating role: {value}")
        if value not in ['participant', 'creator']:
            logger.error(f"Invalid role: {value}")
            raise HTTPException(status_code=400, detail='Role must be "participant" or "creator"')
        return value

    @field_validator('password')
    def validate_password(cls, value: str):
        logger.debug(f"Validating password length: {len(value)}")
        if len(value) < 6:
            logger.error(f"Password too short: length={len(value)}")
            raise HTTPException(status_code=400, detail='Password must be at least 6 characters')
        return value

class TestSchema(BaseModel):
    title: str
    description: Optional[str] = None
    time_limit: Optional[int] = None
    shuffle_questions: bool = False

    @field_validator('title')
    def validate_title(cls, value: str):
        logger.debug(f"Validating title: {value}")
        if not (1 <= len(value) <= 200):
            logger.error(f"Invalid title length: {len(value)}")
            raise HTTPException(status_code=400, detail='Title length must be between 1 and 200 characters')
        return value

    @field_validator('time_limit')
    def validate_time_limit(cls, value: Optional[int]):
        logger.debug(f"Validating time_limit: {value}")
        if value is not None and value <= 0:
            logger.error(f"Invalid time_limit: {value}")
            raise HTTPException(status_code=400, detail='Time limit must be positive')
        return value

class QuestionSchema(BaseModel):
    text: str
    type: str
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None

    @field_validator('type')
    def validate_type(cls, value: str):
        logger.debug(f"Validating question type: {value}")
        if value not in ['open', 'multiple_choice']:
            logger.error(f"Invalid question type: {value}")
            raise HTTPException(status_code=400, detail='Type must be "open" or "multiple_choice"')
        return value

    @field_validator('options')
    def validate_options(cls, value: Optional[List[str]], values: dict):
        logger.debug(f"Validating options: {value}, type={values.get('type')}")
        if values.get('type') == 'multiple_choice':
            if not value or len(value) < 2 or len(value) > 5:
                logger.error(f"Invalid options count: {len(value) if value else 0}")
                raise HTTPException(status_code=400, detail='Multiple choice questions must have 2-5 options')
            if values.get('correct_answer') not in value:
                logger.error(f"Correct answer not in options: {values.get('correct_answer')}")
                raise HTTPException(status_code=400, detail='Correct answer must be one of the options')
        return value

class AnswerSchema(BaseModel):
    question_id: int
    answer: str
    answer_time: Optional[float] = None

    @field_validator('answer')
    def validate_answer(cls, value: str):
        logger.debug(f"Validating answer length: {len(value)}")
        if len(value) > 200:
            logger.error(f"Answer too long: length={len(value)}")
            raise HTTPException(status_code=400, detail='Answer length must not exceed 200 characters')
        return value

    @field_validator('answer_time')
    def validate_answer_time(cls, value: Optional[float]):
        logger.debug(f"Validating answer_time: {value}")
        if value is not None and value < 0:
            logger.error(f"Invalid answer_time: {value}")
            raise HTTPException(status_code=400, detail='Answer time must be non-negative')
        return value