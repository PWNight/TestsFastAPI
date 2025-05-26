from fastapi import Request, HTTPException
import logging
import aiomysql

logger = logging.getLogger('app.utils')

def get_language(request: Request) -> str:
    lang = request.headers.get('accept-language', 'ru').split(',')[0]
    logger.debug(f"Extracted language from request: {lang}", extra={'request_id': getattr(request.state, 'request_id', 'unknown')})
    return lang

def translate_message(message: str, lang: str) -> str:
    logger.debug(f"Translating message: {message} for language: {lang}", extra={'request_id': 'unknown'})
    translations = {
        'ru': {
            'user_registered': 'Пользователь успешно зарегистрирован',
            'invalid_credentials': 'Неверные учетные данные',
            'test_created': 'Тест успешно создан',
            'test_updated': 'Тест успешно обновлен',
            'test_deleted': 'Тест успешно удален',
            'test_not_found': 'Тест не найден',
            'no_permission': 'Нет прав',
            'validation_error': 'Ошибка валидации',
            'api_documentation': 'Документация API',
            'user_not_found': 'Пользователь не найден'
        },
        'en': {
            'user_registered': 'User registered successfully',
            'invalid_credentials': 'Invalid credentials',
            'test_created': 'Test created successfully',
            'test_updated': 'Test updated successfully',
            'test_deleted': 'Test deleted successfully',
            'test_not_found': 'Test not found',
            'no_permission': 'No permission',
            'validation_error': 'Validation error',
            'api_documentation': 'API documentation',
            'user_not_found': 'User not found'
        }
    }
    translated = translations.get(lang, translations['ru']).get(message, message)
    logger.debug(f"Translated message: {translated}")
    return translated

async def handle_db_error(e: Exception, request_id: str = 'unknown') -> HTTPException:
    logger.error(f"Database error: {str(e)}", extra={'request_id': request_id}, exc_info=True)
    if isinstance(e, aiomysql.OperationalError):
        return HTTPException(status_code=503, detail="Database unavailable")
    elif isinstance(e, aiomysql.IntegrityError):
        return HTTPException(status_code=400, detail="Database integrity error")
    return HTTPException(status_code=500, detail="Internal database error")

async def check_creator_permission(cursor, user_id: int, test_id: int | None = None, lang: str = 'ru', request_id: str = 'unknown'):
    logger.debug(f"Checking creator permission for user_id={user_id}, test_id={test_id}", extra={'request_id': request_id})
    try:
        await cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        user = await cursor.fetchone()

        if not user or user['role'] != 'creator':
            logger.warning(f"No permission: User ID={user_id} is not a creator", extra={'request_id': request_id})
            raise HTTPException(status_code=403, detail=translate_message('no_permission', lang))

        if test_id:
            await cursor.execute("SELECT creator_id FROM tests WHERE id = %s", (test_id,))
            test = await cursor.fetchone()

            if not test or test['creator_id'] != user_id:
                logger.warning(f"Test not found or not owned by user ID={user_id}, Test ID={test_id}", extra={'request_id': request_id})
                raise HTTPException(status_code=404, detail=translate_message('test_not_found', lang))
    except Exception as e:
        logger.error(f"Error checking creator permission: {str(e)}", extra={'request_id': request_id}, exc_info=True)
        raise

async def check_participant_permission(cursor, user_id: int, lang: str, request_id: str = 'unknown'):
    logger.debug(f"Checking participant permission for user_id={user_id}", extra={'request_id': request_id})
    try:
        await cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        user = await cursor.fetchone()

        if not user or user['role'] != 'participant':
            logger.warning(f"No permission: User ID={user_id} is not a participant", extra={'request_id': request_id})
            raise HTTPException(status_code=403, detail=translate_message('no_permission', lang))
    except Exception as e:
        logger.error(f"Error checking participant permission: {str(e)}", extra={'request_id': request_id}, exc_info=True)
        raise