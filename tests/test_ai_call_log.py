"""The ai_call_logs plugin must capture model/tool calls without breaking a run.

Two things are worth guarding here: that streaming chunks don't each become a
row (one chat would write hundreds), and that every payload actually survives
the trip into the JSONB column.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from sqlalchemy import delete, select

from config import settings
from db.models import AiCallLog
from hisho_agents import ai_log_plugin
from hisho_agents.ai_log_plugin import AiCallLogPlugin


class _SpySessions:
    """Callable stand-in for AsyncSessionLocal that records added rows."""

    def __init__(self):
        self.records = []

    def __call__(self):
        records = self.records

        class _Ctx:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            def add(self, obj):
                records.append(obj)

            async def commit(self):
                pass

        return _Ctx()


def _context(agent="letter_agent", invocation_id="inv-1"):
    return SimpleNamespace(
        invocation_id=invocation_id,
        agent_name=agent,
        user_id="user-1",
        session=SimpleNamespace(id="sess-1"),
    )


def _request():
    return LlmRequest(
        model="ollama_chat/qwen3:4b",
        contents=[
            types.Content(role="user", parts=[types.Part(text="write a letter")])
        ],
        config=types.GenerateContentConfig(system_instruction="you write letters"),
    )


def test_model_request_is_captured(monkeypatch):
    spy = _SpySessions()
    monkeypatch.setattr(ai_log_plugin, "AsyncSessionLocal", spy)

    asyncio.run(
        AiCallLogPlugin().before_model_callback(
            callback_context=_context(), llm_request=_request()
        )
    )

    record = spy.records[0]
    assert record.kind == "model_request"
    assert record.agent == "letter_agent"
    assert record.session_id == "sess-1"
    assert record.payload["contents"][0]["parts"][0]["text"] == "write a letter"
    assert record.payload["system_instruction"] == "you write letters"
    json.dumps(record.payload)  # must survive the JSONB column


def test_streaming_chunks_are_not_logged_individually(monkeypatch):
    spy = _SpySessions()
    monkeypatch.setattr(ai_log_plugin, "AsyncSessionLocal", spy)
    plugin = AiCallLogPlugin()

    for _ in range(50):
        asyncio.run(
            plugin.after_model_callback(
                callback_context=_context(),
                llm_response=LlmResponse(
                    content=types.Content(role="model", parts=[types.Part(text="ru")]),
                    partial=True,
                ),
            )
        )
    assert spy.records == []

    asyncio.run(
        plugin.after_model_callback(
            callback_context=_context(),
            llm_response=LlmResponse(
                content=types.Content(role="model", parts=[types.Part(text="full")]),
                partial=False,
            ),
        )
    )
    assert len(spy.records) == 1
    assert spy.records[0].payload["text"] == "full"


def test_thoughts_are_kept_out_of_the_response_text(monkeypatch):
    spy = _SpySessions()
    monkeypatch.setattr(ai_log_plugin, "AsyncSessionLocal", spy)

    asyncio.run(
        AiCallLogPlugin().after_model_callback(
            callback_context=_context(),
            llm_response=LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(text="weighing options", thought=True),
                        types.Part(text="Dear Sir,"),
                    ],
                )
            ),
        )
    )

    payload = spy.records[0].payload
    assert payload["text"] == "Dear Sir,"
    assert payload["thoughts"] == "weighing options"


def test_tool_call_round_trips_into_the_database(monkeypatch):
    """The real column, the real driver — a payload JSONB rejects would only
    surface in production otherwise."""

    async def main():
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        engine = create_async_engine(
            settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1),
            echo=False,
        )
        maker = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
        monkeypatch.setattr(ai_log_plugin, "AsyncSessionLocal", maker)
        try:
            await AiCallLogPlugin().after_tool_callback(
                tool=SimpleNamespace(name="create_letter_brief"),
                tool_args={"user_facts": {"duration": "6 hours"}},
                tool_context=_context(invocation_id="inv-db-test"),
                result={"result": "Brief created"},
            )
            async with maker() as session:
                rows = (
                    (
                        await session.execute(
                            select(AiCallLog).where(
                                AiCallLog.invocation_id == "inv-db-test"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                await session.execute(
                    delete(AiCallLog).where(AiCallLog.invocation_id == "inv-db-test")
                )
                await session.commit()
            return rows
        finally:
            await engine.dispose()

    rows = asyncio.run(main())
    assert len(rows) == 1
    assert rows[0].kind == "tool_result"
    assert rows[0].tool_name == "create_letter_brief"
    assert rows[0].payload["args"]["user_facts"] == {"duration": "6 hours"}


def test_a_failing_write_does_not_raise(monkeypatch):
    """Logging is best-effort; a DB outage must not kill the chat."""

    class _Boom:
        def __call__(self):
            raise RuntimeError("database is gone")

    monkeypatch.setattr(ai_log_plugin, "AsyncSessionLocal", _Boom())

    asyncio.run(
        AiCallLogPlugin().before_tool_callback(
            tool=SimpleNamespace(name="x"), tool_args={}, tool_context=_context()
        )
    )


@pytest.mark.parametrize(
    "value,expected",
    [({"a": 1}, {"a": 1}), ([1, "two"], [1, "two"]), (None, None), ("s", "s")],
)
def test_jsonable_leaves_plain_data_alone(value, expected):
    assert ai_log_plugin._jsonable(value) == expected
