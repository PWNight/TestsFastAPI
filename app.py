import logging
import os
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request, Response
from routes.auth import auth_router
from routes.tests import tests_router
from routes.test_execution import test_execution_router
from routes.api_docs import api_docs_router
from db import init_db
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'app.log')

logger = logging.getLogger('app')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

app = FastAPI(title="Test Platform API", version="1.0.0")

# Обработчик жизненного цикла
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('Starting application and initializing database')
    await init_db()
    yield
    logger.info('Application shutdown')

app.lifespan = lifespan

# Логирование запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    body = {}
    if request.method in ["POST", "PUT"]:
        try:
            # Проверяем, что Content-Type указывает на JSON
            content_type = request.headers.get("Content-Type", "")
            if "application/json" in content_type:
                body_content = await request.body()
                if body_content:  # Проверяем, что тело не пустое
                    body = await request.json()
                else:
                    body = {"error": "Empty request body"}
            else:
                body = {"error": f"Invalid Content-Type: {content_type}"}
        except Exception as e:
            logger.warning(f"Failed to parse request body as JSON: {e}")
            body = {"error": f"Invalid JSON: {str(e)}"}
    logger.info(f'Request: {request.method} {request.url.path} - Query: {request.query_params} - Body: {body}')
    response = await call_next(request)
    logger.info(f'Response: {request.method} {request.url.path} - Status: {response.status_code}')
    return response

# Регистрация маршрутов
app.include_router(auth_router, prefix="/api/auth")
app.include_router(tests_router, prefix="/api")
app.include_router(test_execution_router, prefix="/api")
app.include_router(api_docs_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)