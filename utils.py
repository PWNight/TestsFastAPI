from fastapi import Request

def get_language(request: Request):
    return request.headers.get('accept-language', 'ru').split(',')[0]

def translate_message(message, lang):
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
            'register_user': 'Регистрация нового пользователя',
            'login_user': 'Авторизация пользователя',
            'create_test': 'Создание нового теста',
            'update_test': 'Обновление существующего теста',
            'delete_test': 'Удаление теста',
            'start_test': 'Начало прохождения теста',
            'submit_test': 'Отправка ответов на тест',
            'get_test_stats': 'Получение статистики по тесту',
            'export_test_stats': 'Экспорт статистики теста'
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
            'register_user': 'Register a new user',
            'login_user': 'Authenticate a user',
            'create_test': 'Create a new test',
            'update_test': 'Update an existing test',
            'delete_test': 'Delete a test',
            'start_test': 'Start a test',
            'submit_test': 'Submit test answers',
            'get_test_stats': 'Retrieve test statistics',
            'export_test_stats': 'Export test statistics'
        }
    }
    return translations.get(lang, translations['ru']).get(message, message)