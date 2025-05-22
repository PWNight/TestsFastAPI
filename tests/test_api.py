import pytest
import aiomysql
import jwt
import bcrypt
from fastapi.testclient import TestClient
from app import app, db_config
import os

@pytest.fixture
async def db():
    pool = await aiomysql.create_pool(**db_config)
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            yield cursor
        conn.close()
    pool.close()
    await pool.wait_closed()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
async def creator_token(db):
    async with db:
        email = "creator@test.com"
        password = "password123"
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        await db.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s)",
            (email, password_hash, 'creator')
        )
        user_id = db._last_insert_id
        await db._connection.commit()
        token = jwt.encode({'sub': user_id, 'exp': 3600 * 24}, os.getenv('JWT_SECRET_KEY'), algorithm='HS256')
        return token

@pytest.fixture
async def participant_token(db):
    async with db:
        email = "participant@test.com"
        password = "password123"
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        await db.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s)",
            (email, password_hash, 'participant')
        )
        user_id = db._last_insert_id
        await db._connection.commit()
        token = jwt.encode({'sub': user_id, 'exp': 3600 * 24}, os.getenv('JWT_SECRET_KEY'), algorithm='HS256')
        return token

@pytest.mark.asyncio
async def test_register(client):
    response = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "password123",
        "role": "creator"
    })
    assert response.status_code == 200
    assert response.json()['message'] == "User registered successfully"

@pytest.mark.asyncio
async def test_login(client):
    response = client.post("/api/auth/login", json={
        "email": "creator@test.com",
        "password": "password123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

@pytest.mark.asyncio
async def test_create_test(client, creator_token, db):
    response = client.post("/api/tests", json={
        "title": "Test 1",
        "questions": [
            {"text": "Question 1", "type": "open", "correct_answer": "Answer"},
            {"text": "Question 2", "type": "multiple_choice", "options": ["A", "B"], "correct_answer": "A"}
        ]
    }, headers={"Authorization": f"Bearer {creator_token}"})
    assert response.status_code == 200
    assert response.json()['message'] == "Test created successfully"
    test_id = response.json()['test_id']
    async with db:
        await db.execute("SELECT id FROM tests WHERE id = %s", (test_id,))
        assert await db.fetchone() is not None

@pytest.mark.asyncio
async def test_update_test(client, creator_token, db):
    async with db:
        await db.execute(
            "INSERT INTO tests (title, creator_id) VALUES (%s, %s)",
            ("Test 1", 1)
        )
        test_id = db._last_insert_id
        await db._connection.commit()
    response = client.put(f"/api/tests/{test_id}", json={
        "title": "Updated Test",
        "questions": [
            {"text": "Updated Question", "type": "open", "correct_answer": "Answer"}
        ]
    }, headers={"Authorization": f"Bearer {creator_token}"})
    assert response.status_code == 200
    assert response.json()['message'] == "Test updated successfully"

@pytest.mark.asyncio
async def test_delete_test(client, creator_token, db):
    async with db:
        await db.execute(
            "INSERT INTO tests (title, creator_id) VALUES (%s, %s)",
            ("Test 1", 1)
        )
        test_id = db._last_insert_id
        await db._connection.commit()
    response = client.delete(f"/api/tests/{test_id}", headers={"Authorization": f"Bearer {creator_token}"})
    assert response.status_code == 200
    assert response.json()['message'] == "Test deleted successfully"

@pytest.mark.asyncio
async def test_start_test(client, participant_token, db):
    async with db:
        await db.execute(
            "INSERT INTO tests (title, creator_id) VALUES (%s, %s)",
            ("Test 1", 1)
        )
        test_id = db._last_insert_id
        await db.execute(
            "INSERT INTO questions (test_id, text, type, correct_answer) VALUES (%s, %s, %s, %s)",
            (test_id, "Question 1", "open", "Answer")
        )
        await db._connection.commit()
    response = client.post(f"/api/tests/{test_id}/start", headers={"Authorization": f"Bearer {participant_token}"})
    assert response.status_code == 200
    assert "questions" in response.json()

@pytest.mark.asyncio
async def test_submit_test(client, participant_token, db):
    async with db:
        await db.execute(
            "INSERT INTO tests (title, creator_id) VALUES (%s, %s)",
            ("Test 1", 1)
        )
        test_id = db._last_insert_id
        await db.execute(
            "INSERT INTO questions (test_id, text, type, correct_answer) VALUES (%s, %s, %s, %s)",
            (test_id, "Question 1", "open", "Answer")
        )
        question_id = db._last_insert_id
        await db.execute(
            "INSERT INTO test_attempts (user_id, test_id) VALUES (%s, %s)",
            (2, test_id)
        )
        await db._connection.commit()
    response = client.post(f"/api/tests/{test_id}/submit", json={
        "answers": [
            {"question_id": question_id, "answer": "Answer", "answer_time": 10.0}
        ]
    }, headers={"Authorization": f"Bearer {participant_token}"})
    assert response.status_code == 200
    assert "score" in response.json()

@pytest.mark.asyncio
async def test_get_stats(client, creator_token, db):
    async with db:
        await db.execute(
            "INSERT INTO tests (title, creator_id) VALUES (%s, %s)",
            ("Test 1", 1)
        )
        test_id = db._last_insert_id
        await db._connection.commit()
    response = client.get(f"/api/tests/{test_id}/stats", headers={"Authorization": f"Bearer {creator_token}"})
    assert response.status_code == 200
    assert "average_score" in response.json()

@pytest.mark.asyncio
async def test_export_stats(client, creator_token, db):
    async with db:
        await db.execute(
            "INSERT INTO tests (title, creator_id) VALUES (%s, %s)",
            ("Test 1", 1)
        )
        test_id = db._last_insert_id
        await db.execute(
            "INSERT INTO test_attempts (user_id, test_id, score) VALUES (%s, %s, %s)",
            (2, test_id, 80.0)
        )
        await db._connection.commit()
    for format in ["csv", "json", "excel"]:
        response = client.get(f"/api/tests/{test_id}/stats/export?format={format}", headers={"Authorization": f"Bearer {creator_token}"})
        assert response.status_code == 200
        if format == "json":
            assert isinstance(response.json(), list)
        else:
            assert response.headers['content-type'] in ["text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]

@pytest.mark.asyncio
async def test_api_docs(client):
    response = client.get("/api")
    assert response.status_code == 200
    assert "openapi" in response.json()