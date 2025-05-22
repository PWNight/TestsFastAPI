import aiomysql
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger('app.db')
logger.setLevel(logging.INFO)

db_config = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'user': os.getenv('DB_USER', 'pwnight'),
    'password': os.getenv('DB_PASSWORD', 'pwnight'),
    'db': os.getenv('DB_NAME', 'tests'),
    'charset': os.getenv('DB_CHARSET', 'utf8mb4'),
    'cursorclass': aiomysql.DictCursor
}

async def check_index_exists(cursor, table_name, index_name):
    await cursor.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = %s", (index_name,))
    exists = await cursor.fetchone() is not None
    logger.info(f"Checked index {index_name} on table {table_name}: {'exists' if exists else 'does not exist'}")
    return exists

async def init_db():
    try:
        logger.info('Connecting to MySQL server')
        conn = await aiomysql.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            charset=db_config['charset']
        )
        async with conn.cursor() as cursor:
            logger.info('Creating database if not exists')
            await cursor.execute("CREATE DATABASE IF NOT EXISTS tests CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")

        conn.close()
        logger.info('Connecting to database tests')
        pool = await aiomysql.create_pool(**db_config)

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                logger.info('Creating table users')
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password_hash VARCHAR(128) NOT NULL,
                        role VARCHAR(20) NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.info('Creating table tests')
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tests (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        creator_id INT NOT NULL,
                        time_limit INT,
                        shuffle_questions BOOLEAN DEFAULT FALSE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                logger.info('Creating table questions')
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS questions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        test_id INT NOT NULL,
                        text TEXT NOT NULL,
                        type VARCHAR(20) NOT NULL,
                        options JSON,
                        correct_answer TEXT,
                        FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE
                    )
                """)
                logger.info('Creating table test_attempts')
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_attempts (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        test_id INT NOT NULL,
                        score FLOAT,
                        start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        end_time DATETIME,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE
                    )
                """)
                logger.info('Creating table answers')
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS answers (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        attempt_id INT NOT NULL,
                        question_id INT NOT NULL,
                        answer VARCHAR(200) NOT NULL,
                        is_correct BOOLEAN,
                        answer_time FLOAT,
                        FOREIGN KEY (attempt_id) REFERENCES test_attempts(id) ON DELETE CASCADE,
                        FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
                    )
                """)
                logger.info('Creating indexes')
                if not await check_index_exists(cursor, 'users', 'idx_user_email'):
                    await cursor.execute("CREATE INDEX idx_user_email ON users(email)")
                if not await check_index_exists(cursor, 'tests', 'idx_test_creator'):
                    await cursor.execute("CREATE INDEX idx_test_creator ON tests(creator_id)")
                if not await check_index_exists(cursor, 'questions', 'idx_question_test'):
                    await cursor.execute("CREATE INDEX idx_question_test ON questions(test_id)")
                if not await check_index_exists(cursor, 'test_attempts', 'idx_attempt_user_test'):
                    await cursor.execute("CREATE INDEX idx_attempt_user_test ON test_attempts(user_id, test_id)")

            await conn.commit()
            logger.info('Database initialized successfully')

    except Exception as e:
        logger.error(f'Database error: {e}')
    finally:
        pool.close()
        await pool.wait_closed()
        logger.info('Database connection closed')