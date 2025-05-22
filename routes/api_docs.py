from fastapi import APIRouter, Request
from fastapi.openapi.utils import get_openapi
from utils import get_language, translate_message
import logging

api_docs_router = APIRouter()
logger = logging.getLogger('app.api_docs')

@api_docs_router.get("/api", summary="API documentation")
async def api_docs(request: Request):
    lang = get_language(request)
    logger.info(f'API documentation requested, language: {lang}')
    return get_openapi(
        title="TestsFastApi",
        version="1.1.5",
        description=translate_message('api_documentation', lang),
        routes=request.app.routes
    )