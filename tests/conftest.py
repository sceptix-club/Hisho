import asyncio
import uuid

import jwt
import pytest
from sqlalchemy import select

from config import settings
from db.models import User
from db.session import AsyncSessionLocal
from api.routes.auth import create_access_token

# For live tests, ensure we use an Ollama model that is actually present.
# The .env default is qwen3:4b but the local Ollama only has qwen2.5:3b.
# Patch the config and already-imported agents to the available model so
# TestClient's lifespan (which creates the Runner) uses a working model.
try:
    from google.adk.models import LiteLlm as _LiteLlm

    _available = _LiteLlm(
        model="ollama_chat/qwen2.5:3b", api_base="http://localhost:11434"
    )
    from config import config as _cfg

    _cfg.worker_model = _available
    _cfg.critic_model = _available
    try:
        from hisho_agents.agent import (
            interactive_email_agent,
            interactive_letter_agent,
            root_agent,
        )

        root_agent.model = _available
        interactive_letter_agent.model = _available
        interactive_email_agent.model = _available
    except Exception:
        pass
    try:
        from hisho_agents.sub_agents.drafting.content_writer import (
            robust_content_writer,
        )
        from hisho_agents.sub_agents.drafting.email_writer import robust_email_writer

        robust_content_writer.model = _available
        robust_email_writer.model = _available
    except Exception:
        pass
except Exception:
    pass


def run(coro):
    return asyncio.run(coro)


TEST_USER_EMAIL = "pytest_session_tester@example.com"


async def _get_or_create_test_user() -> User:
    # Use a loop-local engine to avoid cross-loop Future issues with the global
    # AsyncSessionLocal (asyncpg is loop-bound). This keeps test setup isolated.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

    db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, echo=False)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as db:
            result = await db.execute(select(User).where(User.email == TEST_USER_EMAIL))
            user = result.scalar_one_or_none()
            if user:
                return user
            user = User(
                id=str(uuid.uuid4()),
                username="pytest_session_tester",
                email=TEST_USER_EMAIL,
                full_name="Pytest Session Tester",
                role="user",
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return user
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def test_user():
    user = run(_get_or_create_test_user())
    return user


@pytest.fixture(scope="session")
def token(test_user):
    return create_access_token({"sub": test_user.id})


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as c:
        yield c


Q1 = "Draft a casual leave application for tomorrow for fever"
Q2 = "Make it more formal and add roll number 123 and medical certificate note"
Q3 = "What did we discuss so far? Summarize our conversation"


@pytest.fixture
def demo_queries():
    return {"q1": Q1, "q2": Q2, "q3": Q3}
