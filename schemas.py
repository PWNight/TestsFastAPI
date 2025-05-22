from flask_marshmallow import Marshmallow
from flask import current_app

ma = Marshmallow(current_app)

class UserSchema(ma.Schema):
    class Meta:
        fields = ('id', 'email', 'role')

class TestSchema(ma.Schema):
    class Meta:
        fields = ('id', 'title', 'description', 'creator_id', 'time_limit', 'shuffle_questions')

class QuestionSchema(ma.Schema):
    class Meta:
        fields = ('id', 'test_id', 'text', 'type', 'options', 'correct_answer')

class AnswerSchema(ma.Schema):
    class Meta:
        fields = ('question_id', 'answer')

user_schema = UserSchema()
test_schema = TestSchema()
question_schema = QuestionSchema(many=True)
answer_schema = AnswerSchema(many=True)