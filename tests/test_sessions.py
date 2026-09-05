"""
Session backend tests — verify ADK session handling is correct.

Run:  uv run pytest tests/test_sessions.py -v
Requires: Postgres (settings.database_url) for the integration tests.
Unit tests for `_events_to_messages` run with no infra.

ADK contract being verified (google.adk.sessions.DatabaseSessionService):
- create_session / get_session / list_sessions / delete_session
- Runner with auto_create_session=True still validates supplied session_id
  (main.py:123 — GET before run_async)
- _events_to_messages correctly maps stored ADK Events -> ChatMessage shape
  consumed by GET /sessions/{id} (what the frontend uses on resume)
- Sessions are isolated per user_id (adk key = app_name + user_id + session_id)
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from google.adk.events import Event
from google.genai import types

from config import settings

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.run(coro)


def make_user_event(text: str) -> Event:
    return Event(
        author="user",
        content=types.Content(role="user", parts=[types.Part(text=text)]),
    )


def make_assistant_event(text: str, thought: bool = False) -> Event:
    part = types.Part(text=text)
    # genai Part has `thought` field - set via model kwargs
    if thought:
        part = types.Part(text=text, thought=True)  # type: ignore[call-arg]
    return Event(
        author="assistant",
        content=types.Content(role="model", parts=[types.Part(text=text) if not thought else part]),
    )


def make_tool_call_event(name: str, args: dict | None = None) -> Event:
    args = args or {}
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    return Event(
        author="assistant",
        content=types.Content(role="model", parts=[part]),
    )


def make_tool_call_and_text_event(name: str, text: str) -> Event:
    # One event can carry both function_call and text across parts - but here we
    # use two parts to exercise the _events_to_messages loop
    call_part = types.Part(function_call=types.FunctionCall(name=name, args={}))
    text_part = types.Part(text=text)
    return Event(
        author="assistant",
        content=types.Content(role="model", parts=[call_part, text_part]),
    )


# For ephemeral user creation (isolated per test) to avoid DB pollution
async def _create_ephemeral_user() -> tuple:
    """Create a throwaway user directly in DB, return (user, token)."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from db.models import User
    from api.routes.auth import create_access_token

    db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, echo=False)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        uid = str(uuid.uuid4())
        async with maker() as db:
            user = User(
                id=uid,
                username=f"ephemeral_{uid[:8]}",
                email=f"ephemeral_{uid[:8]}@example.com",
                full_name="Ephemeral User",
                role="user",
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            token = create_access_token({"sub": user.id})
            return user, token
    finally:
        await engine.dispose()


async def _delete_ephemeral_user(user_id: str):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import delete
    from db.models import User

    db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, echo=False)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as db:
            # ADK sessions are not FK-linked to users table, but clean up anyway
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Isolated ADK helpers — create sessions via a *separate* DatabaseSessionService
# so we don't share the server's asyncpg engine across event loops.
# The server's lifespan engine is bound to the TestClient portal's loop;
# calling it via asyncio.run() creates a new loop -> "attached to different loop".
# Using an isolated service per run hits the same Postgres DB but with a
# loop-local engine, which is safe.
# ---------------------------------------------------------------------------

async def _isolated_create_session(user_id: str, session_id: str, events: list[Event] | None = None):
    from google.adk.sessions import DatabaseSessionService

    db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    svc = DatabaseSessionService(db_url=db_url)
    try:
        sess = await svc.create_session(app_name="hisho", user_id=user_id, session_id=session_id)
        if events:
            for ev in events:
                # Re-fetch to avoid stale-marker check after each append
                sess = await svc.get_session(app_name="hisho", user_id=user_id, session_id=session_id)
                await svc.append_event(sess, ev)
        return sess
    finally:
        await svc.close()


async def _isolated_delete_session(user_id: str, session_id: str):
    from google.adk.sessions import DatabaseSessionService

    db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    svc = DatabaseSessionService(db_url=db_url)
    try:
        await svc.delete_session(app_name="hisho", user_id=user_id, session_id=session_id)
    finally:
        await svc.close()


# ---------------------------------------------------------------------------
# UNIT — _events_to_messages
# ---------------------------------------------------------------------------

class TestEventsToMessages:
    """Pure unit tests for main._events_to_messages — no DB, no LLM."""

    def test_empty_events_returns_empty(self):
        from main import _events_to_messages

        assert _events_to_messages([]) == []

    def test_single_user_message(self):
        from main import _events_to_messages

        events = [make_user_event("hello")]
        msgs = _events_to_messages(events)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["text"] == "hello"
        assert msgs[0]["status"] == "complete"

    def test_user_then_assistant(self):
        from main import _events_to_messages

        events = [make_user_event("hi"), make_assistant_event("hello back")]
        msgs = _events_to_messages(events)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["text"] == "hello back"

    def test_assistant_groups_consecutive_events(self):
        """ADK emits assistant content across multiple events for one turn;
        _events_to_messages should collapse them into one assistant message
        unless a new user message intervenes."""
        from main import _events_to_messages

        events = [
            make_user_event("q1"),
            make_assistant_event("part a"),
            make_assistant_event("part b"),  # overwrites text per impl (reply["text"]=text)
        ]
        msgs = _events_to_messages(events)
        assert len(msgs) == 2
        # second assistant event overwrites text (not appends) — current impl
        assert msgs[1]["text"] == "part b"

    def test_thought_parts_excluded_from_text(self):
        from main import _events_to_messages

        # assistant thought should not appear in text
        thought_event = Event(
            author="assistant",
            content=types.Content(
                role="model",
                parts=[types.Part(text="secret reasoning", thought=True)],  # type: ignore[call-arg]
            ),
        )
        events = [make_user_event("hi"), thought_event, make_assistant_event("answer")]
        msgs = _events_to_messages(events)
        # thought event has no non-thought text => creates an assistant bubble with empty text
        # but the implementation skips events without content/parts? No — thought is filtered
        # let's assert answer is present and reasoning not leaked
        assert any(m["text"] == "answer" for m in msgs if m["role"] == "assistant")
        assert not any("secret reasoning" in m["text"] for m in msgs)

    def test_tool_calls_attached_to_assistant_message(self):
        from main import _events_to_messages

        events = [
            make_user_event("find letters"),
            make_tool_call_event("find_similar_letters", {"q": "leave"}),
            make_assistant_event("found 2 letters"),
        ]
        msgs = _events_to_messages(events)
        ass_msgs = [m for m in msgs if m["role"] == "assistant"]
        assert len(ass_msgs) == 1
        assert len(ass_msgs[0]["tool_calls"]) == 1
        assert ass_msgs[0]["tool_calls"][0]["name"] == "find_similar_letters"
        assert ass_msgs[0]["text"] == "found 2 letters"

    def test_tool_call_and_text_same_turn(self):
        from main import _events_to_messages

        events = [
            make_user_event("q"),
            make_tool_call_and_text_event("my_tool", "final answer"),
        ]
        msgs = _events_to_messages(events)
        # ADK test: get_function_calls extracts call; text extraction extracts "final answer"
        assert msgs[-1]["tool_calls"][0]["name"] == "my_tool"
        assert msgs[-1]["text"] == "final answer"

    def test_final_status_json_unwrapped(self):
        """Agent often returns JSON string like {"final_status": "done"} — should unwrap."""
        from main import _events_to_messages

        payload = json.dumps({"final_status": "Letter ready", "extra": "ignore"})
        events = [make_user_event("draft"), make_assistant_event(payload)]
        msgs = _events_to_messages(events)
        assert msgs[-1]["text"] == "Letter ready"

    def test_final_status_json_missing_key_kept_as_is(self):
        from main import _events_to_messages

        payload = json.dumps({"other": "value"})
        events = [make_user_event("q"), make_assistant_event(payload)]
        msgs = _events_to_messages(events)
        assert msgs[-1]["text"] == payload

    def test_invalid_json_kept_as_is(self):
        from main import _events_to_messages

        events = [make_user_event("q"), make_assistant_event("not json {{")]
        msgs = _events_to_messages(events)
        assert msgs[-1]["text"] == "not json {{"

    def test_events_without_content_skipped(self):
        from main import _events_to_messages

        events = [
            make_user_event("hi"),
            Event(author="assistant", content=None),  # type: ignore[arg-type]
            Event(author="assistant", content=types.Content(role="model", parts=[])),
            make_assistant_event("ok"),
        ]
        msgs = _events_to_messages(events)
        # only hi + ok should survive
        assert len([m for m in msgs if m["role"] == "user"]) == 1
        assert len([m for m in msgs if m["role"] == "assistant"]) == 1
        assert msgs[-1]["text"] == "ok"

    def test_empty_user_text_skipped(self):
        from main import _events_to_messages

        events = [
            Event(author="user", content=types.Content(role="user", parts=[types.Part(text="")]))
        ]
        msgs = _events_to_messages(events)
        assert msgs == []

    def test_resume_shape_matches_frontend_chatmessage(self):
        """GET /sessions/{id} must return {id, messages: ChatMessage[]}
        where each ChatMessage has role/text/thought/tool_calls/status.
        This is what chat.svelte expects on resume."""
        from main import _events_to_messages

        events = [
            make_user_event("Draft a casual leave for tomorrow"),
            make_assistant_event("Here is a draft..."),
            make_user_event("Make it more formal"),
            make_assistant_event(json.dumps({"final_status": "Done — formal draft"})),
        ]
        msgs = _events_to_messages(events)
        assert len(msgs) == 4
        for m in msgs:
            assert set(["role", "text", "thought", "tool_calls", "status"]).issubset(m.keys())
            assert m["role"] in ("user", "assistant")
            assert m["status"] == "complete"
            assert isinstance(m["text"], str)
            assert isinstance(m["tool_calls"], list)

    def test_multiturn_conversation_order_preserved(self):
        from main import _events_to_messages

        events = [
            make_user_event("turn1"),
            make_assistant_event("resp1"),
            make_user_event("turn2"),
            make_assistant_event("resp2"),
            make_user_event("turn3"),
            make_assistant_event("resp3"),
        ]
        msgs = _events_to_messages(events)
        assert [m["text"] for m in msgs] == ["turn1", "resp1", "turn2", "resp2", "turn3", "resp3"]


# ---------------------------------------------------------------------------
# INTEGRATION — /sessions CRUD via ADK DatabaseSessionService
# These hit Postgres but NOT the LLM (sessions created directly via the service).
# ---------------------------------------------------------------------------

class TestSessionEndpoints:
    """Verify the session HTTP API respects ADK semantics and auth."""

    def test_list_sessions_requires_auth(self, client):
        assert client.get("/sessions").status_code == 401

    def test_get_session_requires_auth(self, client):
        assert client.get("/sessions/any-id").status_code == 401

    def test_delete_session_requires_auth(self, client):
        assert client.delete("/sessions/any-id").status_code == 401

    def test_chat_stream_requires_auth(self, client):
        r = client.post("/chat/stream", json={"query": "hi", "session_id": None})
        assert r.status_code == 401

    def test_list_sessions_shape(self, client, auth_headers):
        """GET /sessions returns list of {id, title, last_update} (even if empty)."""
        r = client.get("/sessions", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        for item in body:
            assert "id" in item and "title" in item and "last_update" in item

    def test_get_session_404(self, client, auth_headers):
        r = client.get("/sessions/does-not-exist-123", headers=auth_headers)
        assert r.status_code == 404
        assert "Session not found" in r.text

    def test_delete_session_404(self, client, auth_headers):
        r = client.delete("/sessions/does-not-exist-123", headers=auth_headers)
        assert r.status_code == 404

    def test_chat_stream_invalid_session_returns_404(self, client, auth_headers):
        """POST /chat/stream with a non-existent session_id must 404
        — even though Runner has auto_create_session=True, main.py validates first."""
        r = client.post(
            "/chat/stream",
            json={"query": "hello", "session_id": "00000000-0000-0000-0000-000000000000"},
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert "Session not found" in r.text

    def test_create_and_retrieve_session_via_adk_service(self, client, test_user, token, auth_headers):
        """Create a session via an isolated ADK service (bypasses LLM),
        then verify GET /sessions and GET /sessions/{id} return it correctly."""
        sid = uuid.uuid4().hex
        # isolated helper hits same DB but with loop-local engine
        run(_isolated_create_session(test_user.id, sid, [make_user_event("Draft a leave letter for fever")]))
        try:
            # List should contain our session
            r = client.get("/sessions", headers=auth_headers)
            assert r.status_code == 200
            ids = [s["id"] for s in r.json()]
            assert sid in ids
            # Title should be first user message truncated to 40
            title = next(s["title"] for s in r.json() if s["id"] == sid)
            assert title == "Draft a leave letter for fever"[:40]

            # Get single session — messages shape
            r = client.get(f"/sessions/{sid}", headers=auth_headers)
            assert r.status_code == 200
            body = r.json()
            assert body["id"] == sid
            assert isinstance(body["messages"], list)
            assert len(body["messages"]) == 1
            assert body["messages"][0]["role"] == "user"
            assert body["messages"][0]["text"] == "Draft a leave letter for fever"
        finally:
            run(_isolated_delete_session(test_user.id, sid))

    def test_delete_session_roundtrip(self, client, test_user, auth_headers):
        sid = uuid.uuid4().hex
        run(_isolated_create_session(test_user.id, sid))
        try:
            # ensure exists
            r = client.get(f"/sessions/{sid}", headers=auth_headers)
            assert r.status_code == 200

            # delete
            r = client.delete(f"/sessions/{sid}", headers=auth_headers)
            assert r.status_code == 200
            assert r.json()["deleted"] == sid

            # subsequent get => 404
            r = client.get(f"/sessions/{sid}", headers=auth_headers)
            assert r.status_code == 404

            # subsequent delete => 404
            r = client.delete(f"/sessions/{sid}", headers=auth_headers)
            assert r.status_code == 404
        finally:
            try:
                run(_isolated_delete_session(test_user.id, sid))
            except Exception:
                pass

    def test_session_isolation_per_user(self, client, test_user, auth_headers):
        """Sessions are keyed by (app_name, user_id, session_id) — other users
        must not see each other's sessions (ADK contract)."""
        # Create ephemeral other user
        other_user, other_token = run(_create_ephemeral_user())
        other_headers = {"Authorization": f"Bearer {other_token}"}
        sid = uuid.uuid4().hex
        try:
            run(_isolated_create_session(test_user.id, sid, [make_user_event("secret private message")]))

            # owner can see it
            r = client.get(f"/sessions/{sid}", headers=auth_headers)
            assert r.status_code == 200

            # other user gets 404 (not 200 with empty, not 403 — just not found)
            r = client.get(f"/sessions/{sid}", headers=other_headers)
            assert r.status_code == 404

            # other user cannot delete it
            r = client.delete(f"/sessions/{sid}", headers=other_headers)
            assert r.status_code == 404

            # owner can still delete
            r = client.delete(f"/sessions/{sid}", headers=auth_headers)
            assert r.status_code == 200
        finally:
            try:
                run(_isolated_delete_session(test_user.id, sid))
            except Exception:
                pass
            run(_delete_ephemeral_user(other_user.id))

    def test_list_sessions_limits_to_20_and_sorts_by_time(self, client, test_user, auth_headers):
        """main.py sorts by last_update_time desc and slices [:20]."""
        sids: list[str] = []
        try:
            for i in range(3):
                sid = uuid.uuid4().hex
                sids.append(sid)
                run(_isolated_create_session(test_user.id, sid, [make_user_event(f"msg {i}")]))
                # ensure DB timestamp tick
                asyncio.run(asyncio.sleep(0.05))

            r = client.get("/sessions", headers=auth_headers)
            assert r.status_code == 200
            body = r.json()
            # all our sids should appear
            ids = [s["id"] for s in body]
            for sid in sids:
                assert sid in ids
            # Should be at most 20
            assert len(body) <= 20
            # Should be sorted desc by last_update
            times = [s["last_update"] for s in body]
            assert times == sorted(times, reverse=True)
        finally:
            for sid in sids:
                try:
                    run(_isolated_delete_session(test_user.id, sid))
                except Exception:
                    pass

    def test_chat_stream_without_session_id_does_not_404(self, client, auth_headers):
        """POST /chat/stream without session_id should not 404 — it should
        attempt to run the agent (may error if LLM unavailable, but not 404).
        We mock the runner to avoid needing Ollama."""
        from main import app

        async def fake_run_async(**kwargs):
            # Validate caller passed a new uuid-style session_id
            assert kwargs.get("session_id")
            assert kwargs.get("user_id")
            # Yield a single final response event
            yield Event(
                author="assistant",
                content=types.Content(role="model", parts=[types.Part(text="mocked response")]),
            )

        with patch.object(app.state.runner, "run_async", side_effect=fake_run_async):
            r = client.post(
                "/chat/stream",
                json={"query": "hello", "session_id": None},
                headers=auth_headers,
            )
            # StreamingResponse — status 200 even though body is SSE
            assert r.status_code == 200
            assert "text/event-stream" in r.headers.get("content-type", "")

    def test_chat_stream_resume_existing_session_uses_same_id(self, client, test_user, auth_headers):
        """When resuming with session_id, the runner must be called with that exact id.
        This is the critical path for frontend resume."""
        sid = uuid.uuid4().hex
        run(_isolated_create_session(test_user.id, sid))
        try:
            seen = {}
            from main import app

            async def fake_run_async(**kwargs):
                seen.update(kwargs)
                yield Event(
                    author="assistant",
                    content=types.Content(role="model", parts=[types.Part(text="resume ok")]),
                )

            with patch.object(app.state.runner, "run_async", side_effect=fake_run_async):
                r = client.post(
                    "/chat/stream",
                    json={"query": "follow-up", "session_id": sid},
                    headers=auth_headers,
                )
                assert r.status_code == 200
                assert seen.get("session_id") == sid
                assert seen.get("user_id") == test_user.id
        finally:
            try:
                run(_isolated_delete_session(test_user.id, sid))
            except Exception:
                pass

    def test_get_session_messages_preserves_history_order(self, client, test_user, auth_headers):
        """GET /sessions/{id} should return messages in conversation order
        via _events_to_messages — frontend depends on this for resume rendering."""
        sid = uuid.uuid4().hex
        try:
            run(
                _isolated_create_session(
                    test_user.id,
                    sid,
                    [
                        make_user_event("draft leave"),
                        make_assistant_event("here is draft"),
                        make_user_event("make it formal"),
                        make_assistant_event("here is formal draft"),
                    ],
                )
            )

            r = client.get(f"/sessions/{sid}", headers=auth_headers)
            assert r.status_code == 200
            msgs = r.json()["messages"]
            assert len(msgs) == 4
            assert msgs[0]["text"] == "draft leave"
            assert msgs[0]["role"] == "user"
            assert msgs[1]["text"] == "here is draft"
            assert msgs[1]["role"] == "assistant"
            assert msgs[2]["text"] == "make it formal"
            assert msgs[3]["text"] == "here is formal draft"
        finally:
            try:
                run(_isolated_delete_session(test_user.id, sid))
            except Exception:
                pass
