from fastapi import Request, HTTPException
import logging
import aiomysql

logger = logging.getLogger('app.utils')

def get_language(request: Request) -> str:
    return request.headers.get('accept-language', 'ru').split(',')[0]

def translate_message(message: str, lang: str) -> str:
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
            'api_documentation': 'Документация API'
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
            'api_documentation': 'API documentation'
        }
    }
    return translations.get(lang, translations['ru']).get(message, message)

async def handle_db_error(e: Exception) -> HTTPException:
    """Handle database errors."""
    logger.error(f"Database error: {e}")
    if isinstance(e, aiomysql.OperationalError):
        return HTTPException(status_code=503, detail="Database unavailable")
    return HTTPException(status_code=500, detail="Database error")

async def check_creator_permission(cursor, user_id: int, test_id: int | None = None, lang: str = 'ru'):
    """Check if user is a creator and owns the test (if test_id provided)."""
    await cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    user = await cursor.fetchone()
    if not user or user['role'] != 'creator':
        logger.warning(f'No permission: User ID={user_id} is not a creator')
        raise HTTPException(status_code=403, detail=translate_message('no_permission', lang))
    if test_id:
        await cursor.execute("SELECT creator_id FROM tests WHERE id = %s", (test_id,))
        test = await cursor.fetchone()
        if not test or test['creator_id'] != user_id:
            logger.warning(f'Test not found or not owned by user ID={user_id}, Test ID={test_id}')
            raise HTTPException(status_code=404, detail=translate_message('test_not_found', lang))

async def check_participant_permission(cursor, user_id: int, lang: str):
    """Check if user is a participant."""
    await cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    user = await cursor.fetchone()
    if not user or user['role'] != 'participant':
        logger.warning(f'No permission: User ID={user_id} is not a participant')
        raise HTTPException(status_code=403, detail=translate_message('no_permission', lang))