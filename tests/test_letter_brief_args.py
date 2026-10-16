"""Regression: LLM-supplied tool args are not type-checked by ADK.

The model passed ``user_facts`` as a JSON object. ADK's FunctionTool only
coerces args annotated as pydantic models (function_tool._preprocess_args), so
the dict reached the ``Text`` column and asyncpg raised
``DataError: expected str, got dict``. Normalising happens in the tool itself.

The six text args share one annotation and one exposure, so all of them are
normalised — not just the one that happened to crash first.
"""

import asyncio

import pytest

from hisho_agents.tools import letter_tools
from hisho_agents.tools.letter_tools import _as_text


class _FakeResult:
    """Enough of a Result for the approval-chain lookup to find nothing."""

    def scalar_one_or_none(self):
        return None


class _FakeSession:
    """Stands in for AsyncSessionLocal() and records the Letter without a DB."""

    def __init__(self):
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, *args, **kwargs):
        return _FakeResult()

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass


@pytest.mark.parametrize(
    "value,expected",
    [
        ("already text", "already text"),
        (
            {"duration": "6 hours", "venue": "Kalam Auditorium"},
            '{"duration": "6 hours", "venue": "Kalam Auditorium"}',
        ),
        (["a", "b"], '["a", "b"]'),
        (None, ""),
        (7, "7"),
    ],
)
def test_as_text_normalises(value, expected):
    assert _as_text(value) == expected


def test_brief_stores_text_when_the_model_sends_a_dict(monkeypatch):
    fake = _FakeSession()
    monkeypatch.setattr(letter_tools, "AsyncSessionLocal", lambda: fake)

    asyncio.run(
        letter_tools.create_letter_brief(
            title="Event Permission Request",
            description="Hackathon permission",
            letter_type_id="event_permission_request",
            user_facts={"duration": "6 hours", "venue": "Kalam Auditorium"},
        )
    )

    letter = fake.added[0]
    assert isinstance(letter.user_facts, str)
    assert "6 hours" in letter.user_facts
