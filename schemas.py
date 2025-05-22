from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional

class UserSchema(BaseModel):
    email: EmailStr
    role: str
    password: str

    @field_validator('role')
    def validate_role(self, value: str):
        if value not in ['participant', 'creator']:
            raise ValueError('Role must be "participant" or "creator"')
        return value

    @field_validator('password')
    def validate_password(self, value: str):
        if len(value) < 6:
            raise ValueError('Password must be at least 6 characters')
        return value

class TestSchema(BaseModel):
    title: str
    description: Optional[str] = None
    time_limit: Optional[int] = None
    shuffle_questions: bool = False

    @field_validator('title')
    def validate_title(self, value: str):
        if not (1 <= len(value) <= 200):
            raise ValueError('Title length must be between 1 and 200 characters')
        return value

    @field_validator('time_limit')
    def validate_time_limit(self, value: Optional[int]):
        if value is not None and value <= 0:
            raise ValueError('Time limit must be positive')
        return value

class QuestionSchema(BaseModel):
    text: str
    type: str
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None

    @field_validator('type')
    def validate_type(self, value: str):
        if value not in ['open', 'multiple_choice']:
            raise ValueError('Type must be "open" or "multiple_choice"')
        return value

    @field_validator('options')
    def validate_options(self, value: Optional[List[str]], values: dict):
        if values.get('type') == 'multiple_choice':
            if not value or len(value) < 2 or len(value) > 5:
                raise ValueError('Multiple choice questions must have 2-5 options')
            if values.get('correct_answer') not in value:
                raise ValueError('Correct answer must be one of the options')
        return value

class AnswerSchema(BaseModel):
    question_id: int
    answer: str
    answer_time: Optional[float] = None

    @field_validator('answer')
    def validate_answer(self, value: str):
        if len(value) > 200:
            raise ValueError('Answer length must not exceed 200 characters')
        return value

    @field_validator('answer_time')
    def validate_answer_time(self, value: Optional[float]):
        if value is not None and value < 0:
            raise ValueError('Answer time must be non-negative')
        return value