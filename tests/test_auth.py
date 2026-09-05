import asyncio

import jwt
import pytest

from api.routes import auth as auth_module
from config import settings


def run(coro):
    return asyncio.run(coro)


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}
        self.cookies = {}


async def _fake_db():
    yield None


def test_get_current_user_missing_token():
    req = FakeRequest(headers={})
    with pytest.raises(Exception) as exc:
        run(auth_module.get_current_user(req, _fake_db(), None))
    assert exc.value.status_code == 401


def test_get_current_user_invalid_token():
    req = FakeRequest(headers={"Authorization": "Bearer not-a-jwt"})
    with pytest.raises(Exception) as exc:
        run(auth_module.get_current_user(req, _fake_db(), None))
    assert exc.value.status_code == 401


def test_get_current_user_wrong_secret():
    bad = jwt.encode({"sub": "x"}, "wrong-secret", algorithm="HS256")
    req = FakeRequest(headers={"Authorization": f"Bearer {bad}"})
    with pytest.raises(Exception) as exc:
        run(auth_module.get_current_user(req, _fake_db(), None))
    assert exc.value.status_code == 401


def test_sessions_requires_auth():
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    assert client.get("/sessions").status_code == 401


def test_chat_stream_requires_auth():
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    r = client.post(
        "/chat/stream",
        json={"query": "hi", "user_id": "default", "session_id": None},
    )
    assert r.status_code == 401
