import aiomysql
import logging
import os
from dotenv import load_dotenv
from utils import handle_db_error

load_dotenv()

logger = logging.getLogger('app.db')
logger.setLevel(logging.INFO)

db_config = {
    'host': os.getenv('DB_HOST', os.getenv('DB_HOST')),
    'user': os.getenv('DB_USER', os.getenv('DB_USER')),
    'password': os.getenv('DB_PASSWORD', os.getenv('DB_PASSWORD')),
    'db': os.getenv('DB_NAME', os.getenv('DB_NAME')),
    'charset': os.getenv('DB_CHARSET', os.getenv('DB_CHARSET')),
    'cursorclass': aiomysql.DictCursor
}

pool = None

async def get_db():
    global pool
    if pool is None:
        pool = await aiomysql.create_pool(**db_config)
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            yield cursor

async def init_db():
    global pool
    try:
        logger.info('Connecting to MySQL server')
        async with aiomysql.connect(host=db_config['host'], user=db_config['user'], password=db_config['password'], charset=db_config['charset']) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("CREATE DATABASE IF NOT EXISTS tests CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")

        pool = await aiomysql.create_pool(**db_config)
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password_hash VARCHAR(128) NOT NULL,
                        role VARCHAR(20) NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_user_email (email)
                    )
                """)
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tests (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        creator_id INT NOT NULL,
                        time_limit INT,
                        shuffle_questions BOOLEAN DEFAULT FALSE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE,
                        INDEX idx_test_creator (creator_id)
                    )
                """)
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS questions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        test_id INT NOT NULL,
                        text TEXT NOT NULL,
                        type VARCHAR(20) NOT NULL,
                        options JSON,
                        correct_answer TEXT,
                        FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE,
                        INDEX idx_question_test (test_id)
                    )
                """)
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_attempts (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        test_id INT NOT NULL,
                        score FLOAT,
                        start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        end_time DATETIME,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE,
                        INDEX idx_attempt_user_test (user_id, test_id)
                    )
                """)
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
                await conn.commit()
                logger.info('Database initialized successfully')
    except (aiomysql.OperationalError, aiomysql.IntegrityError) as e:
        raise handle_db_error(e)
    finally:
        if pool:
            pool.close()
            await pool.wait_closed()
            logger.info('Database connection closed')