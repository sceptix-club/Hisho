import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import hisho_agents.tools.docs as docs


class FakeCtx:
    def __init__(self):
        self._state = {}
        self.session = MagicMock()
        self.session.user_id = "u1"
        self.session.state = self._state

    @property
    def state(self):
        return self._state


def run(coro):
    return asyncio.run(coro)


def _fake_service():
    fake = MagicMock()
    fake._client.creds.token = "tok"
    fake.create_document.return_value = {"document_id": "DOC1", "title": "T"}
    fake.fetch_document.return_value = {"body": {"content": [{"endIndex": 5}]}}
    fake.edit_document.return_value = {"document_id": "DOC1"}
    return fake


def test_sync_creates_then_overwrites_same_doc():
    fake = _fake_service()
    with patch.object(docs, "_get_service", AsyncMock(return_value=(fake, None))), patch.object(
        docs, "_after", AsyncMock()
    ), patch.object(docs, "remember_letter", AsyncMock()):
        ctx = FakeCtx()
        r1 = run(docs.sync_letter_to_google_docs("hello world", "Title", tool_context=ctx))
        assert r1["document_id"] == "DOC1"
        assert "docs.google.com" in r1["url"]
        assert ctx._state["google_doc_id"] == "DOC1"

        r2 = run(docs.sync_letter_to_google_docs("revised", "Title", tool_context=ctx))
        assert r2["document_id"] == "DOC1"
        # created once, then overwritten via edit - no duplicate documents
        fake.create_document.assert_called_once()
        fake.edit_document.assert_called_once()


def test_sync_no_user_returns_error():
    with patch.object(docs, "_after", AsyncMock()), patch.object(
        docs, "remember_letter", AsyncMock()
    ):
        r = run(docs.sync_letter_to_google_docs("x", "t", tool_context=None))
        assert "error" in r
        assert "logged in" in r["error"]


def test_sync_user_without_google_returns_error():
    with patch.object(
        docs, "_load_user_tokens", AsyncMock(return_value=(None, None))
    ), patch.object(docs, "_after", AsyncMock()), patch.object(
        docs, "remember_letter", AsyncMock()
    ):
        ctx = FakeCtx()
        r = run(docs.sync_letter_to_google_docs("x", "t", tool_context=ctx))
        assert "error" in r
        assert "Google" in r["error"]
