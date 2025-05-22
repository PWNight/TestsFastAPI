from flask import Flask, request
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from db import init_db
from routes.auth import auth_bp
from routes.tests import tests_bp
from routes.test_execution import test_execution_bp
from routes.api_docs import api_docs_bp
import datetime
import logging
from logging.handlers import RotatingFileHandler
import os

app = Flask(__name__)

# Настройка логирования
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'app.log')

# Создание логгера
logger = logging.getLogger('app')
logger.setLevel(logging.INFO)

# Форматтер для логов
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Обработчик для файла с ротацией (максимум 10 МБ, хранится до 5 резервных копий)
file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Обработчик для вывода в терминал
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Логирование каждого запроса
@app.before_request
def log_request_info():
    logger.info(f'Request: {request.method} {request.path} - Args: {request.args} - JSON: {request.get_json(silent=True)}')

@app.after_request
def log_response_info(response):
    logger.info(f'Response: {request.method} {request.path} - Status: {response.status_code}')
    return response

# Конфигурация
app.config['JWT_SECRET_KEY'] = 'WRhozxmjMcicdalqOBRjv70piyIrCKw3fXw8zsmLPH7peeR5wlqU74tYHGOWHeAX'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(hours=24)

# Инициализация расширений
ma = Marshmallow(app)
jwt = JWTManager(app)

# Регистрация blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(tests_bp, url_prefix='/api')
app.register_blueprint(test_execution_bp, url_prefix='/api')
app.register_blueprint(api_docs_bp)

if __name__ == '__main__':
    logger.info('Starting application and initializing database')
    init_db()  # Инициализация базы данных
    app.run(debug=True)