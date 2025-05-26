import logging
import os
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware  # Импортируем CORSMiddleware
from routes.auth import auth_router
from routes.tests import tests_router
from routes.test_execution import test_execution_router
from routes.api_docs import api_docs_router
from dotenv import load_dotenv

load_dotenv()

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

app = FastAPI(title="TestsFastApi", version="1.2.0")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Разрешённый источник (фронтенд)
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все методы (GET, POST, и т.д.)
    allow_headers=["*"],  # Разрешить все заголовки
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f'Request: {request.method} {request.url.path} - Query: {request.query_params}')
    response = await call_next(request)
    logger.info(f'Response: {request.method} {request.url.path} - Status: {response.status_code}')
    return response

app.include_router(auth_router, prefix="/api/auth")
app.include_router(tests_router, prefix="/api")
app.include_router(test_execution_router, prefix="/api")
app.include_router(api_docs_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)