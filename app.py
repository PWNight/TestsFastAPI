import logging
import os
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from routes.auth import auth_router
from routes.tests import tests_router
from routes.test_execution import test_execution_router
from routes.api_docs import api_docs_router
from dotenv import load_dotenv
import uuid
from contextlib import asynccontextmanager

load_dotenv()

# Конфигурация логирования
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'app.log')

logger = logging.getLogger('app')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - RequestID=%(request_id)s - %(message)s')

file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Чтение CORS настроек из переменных окружения
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')

app = FastAPI(title="TestsFastApi", version="1.2.0")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up")
    yield
    logger.info("Application shutting down")

app.lifespan = lifespan

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id  # Сохраняем request_id для использования в других логах
    logger.info(f"Request: {request.method} {request.url.path} - Query: {request.query_params}", extra={'request_id': request_id})
    try:
        response = await call_next(request)
        logger.info(f"Response: {request.method} {request.url.path} - Status: {response.status_code}", extra={'request_id': request_id})
        return response
    except Exception as e:
        logger.error(f"Unhandled error in request: {request.method} {request.url.path} - Error: {str(e)}", extra={'request_id': request_id}, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

app.include_router(auth_router, prefix="/api/auth")
app.include_router(tests_router, prefix="/api")
app.include_router(test_execution_router, prefix="/api")
app.include_router(api_docs_router)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server")
    uvicorn.run(app)