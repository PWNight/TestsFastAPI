from marshmallow import Schema, fields, validates, ValidationError, validates_schema
import re

class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    email = fields.Email(required=True)
    role = fields.Str(required=True, validate=lambda x: x in ['participant', 'creator'])
    password = fields.Str(required=True, load_only=True, validate=lambda x: len(x) >= 6)

    @validates('email')
    def validate_email(self, value):
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', value):
            raise ValidationError('Invalid email format')

class TestSchema(Schema):
    id = fields.Int(dump_only=True)
    title = fields.Str(required=True, validate=lambda x: 1 <= len(x) <= 200)
    description = fields.Str(allow_none=True)
    creator_id = fields.Int(dump_only=True)
    time_limit = fields.Int(allow_none=True, validate=lambda x: x > 0 if x is not None else True)
    shuffle_questions = fields.Bool(default=False)

class QuestionSchema(Schema):
    id = fields.Int(dump_only=True)
    test_id = fields.Int(dump_only=True)
    text = fields.Str(required=True, validate=lambda x: len(x) > 0)
    type = fields.Str(required=True, validate=lambda x: x in ['open', 'multiple_choice'])
    options = fields.List(fields.Str, allow_none=True)
    correct_answer = fields.Str(allow_none=True)

    @validates_schema
    def validate_options(self, data, **kwargs):
        if data['type'] == 'multiple_choice':
            if not data.get('options') or len(data['options']) < 2 or len(data['options']) > 5:
                raise ValidationError('Multiple choice questions must have 2-5 options')
            if not data.get('correct_answer') or data['correct_answer'] not in data['options']:
                raise ValidationError('Correct answer must be one of the options')

class AnswerSchema(Schema):
    question_id = fields.Int(required=True)
    answer = fields.Str(required=True, validate=lambda x: len(x) <= 200)
    answer_time = fields.Float(allow_none=True, validate=lambda x: x >= 0 if x is not None else True)

user_schema = UserSchema()
test_schema = TestSchema()
question_schema = QuestionSchema(many=True)
answer_schema = AnswerSchema(many=True)