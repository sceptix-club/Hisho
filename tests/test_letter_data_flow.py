"""The data an agent must have in hand to draft a real letter.

The failure this guards: approval_router resolved the right people from the
``officials`` table, but the writer was handed names only — no office, no
address, no date, and no idea who was signing — so it produced a letter shell
full of ``[Placeholders]``.
"""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import delete, select

from config import settings
from db.models import Letter, Official
from hisho_agents.tools import db as tools_db
from hisho_agents.tools import letter_tools
from hisho_agents.tools.db import get_approval_chain_from_db
from hisho_agents.tools.letter_tools import build_writer_request
from hisho_agents.tools.validation_checkers import LetterValidationChecker


def run(coro):
    return asyncio.run(coro)


def test_chain_carries_each_officials_office_and_address(monkeypatch):
    async def main():
        # Loop-local engine: the global AsyncSessionLocal is asyncpg-loop-bound
        # and is already in use by TestClient's loop (see tests/conftest.py).
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
        monkeypatch.setattr(tools_db, "AsyncSessionLocal", maker)
        try:
            chain = await get_approval_chain_from_db("event_permission_request")
            async with maker() as session:
                officials = (
                    (
                        await session.execute(
                            select(Official).where(Official.deleted.is_(False))
                        )
                    )
                    .scalars()
                    .all()
                )
            return chain, officials
        finally:
            await engine.dispose()

    chain, officials = run(main())
    matched = [o for o in officials if o.name in chain]
    assert matched, "the chain resolved no officials — check the seeded data"
    for official in matched:
        assert official.address in chain, f"{official.name}'s address is missing"
        assert official.organization in chain, f"{official.name}'s office is missing"


def test_brief_refuses_an_invented_approval_chain(monkeypatch, test_user):
    """The router sometimes skips get_approval_chain_from_db and makes people up.

    The brief must fall back to the database, not to the model's imagination.
    """

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
        # create_letter_brief opens its own session; point it at this loop's
        # engine so the test never touches the shared one.
        monkeypatch.setattr(letter_tools, "AsyncSessionLocal", maker)
        try:
            created = await letter_tools.create_letter_brief(
                title="Hackathon",
                description="Permission for Rain Of Code",
                letter_type_id="event_permission_request",
                user_facts='{"event": "Rain Of Code"}',
                approval_chain="1. John Smith, Event Coordinator — 123 University Ave",
                style_references="",
                tool_context=SimpleNamespace(
                    session=SimpleNamespace(user_id=test_user.id, id=None)
                ),
            )
            brief_id = created.split("id=")[1].split(" ")[0]
            async with maker() as session:
                chain = (
                    await session.execute(
                        select(Letter.approval_chain).where(Letter.id == brief_id)
                    )
                ).scalar_one()
                # Don't leave this test's brief behind in the dev database.
                await session.execute(delete(Letter).where(Letter.id == brief_id))
                await session.commit()
            return chain
        finally:
            await engine.dispose()

    chain = run(main())
    assert "John Smith" not in chain
    assert "Name:" in chain and "Address:" in chain


def test_writer_falls_back_to_the_latest_pending_brief(test_user):
    """The agent sometimes calls the writer before it has the brief id.

    A made-up id must not cost the user their letter.
    """

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
        run_id = "pytest-brief-fallback"
        now = datetime.now()
        try:
            async with maker() as session:
                session.add_all(
                    [
                        Letter(
                            id="pytestolderbrief",
                            reference_number="LT-OLD",
                            letter_type_id="event_permission_request",
                            title="older",
                            description="d",
                            approved=False,
                            content=None,
                            status="pending",
                            user_id=test_user.id,
                            session_id=run_id,
                            created_at=now - timedelta(hours=1),
                        ),
                        Letter(
                            id="pytestnewerbrief",
                            reference_number="LT-NEW",
                            letter_type_id="event_permission_request",
                            title="newer",
                            description="d",
                            approved=False,
                            content=None,
                            status="pending",
                            user_id=test_user.id,
                            session_id=run_id,
                            created_at=now,
                        ),
                    ]
                )
                await session.commit()

            context = SimpleNamespace(
                session=SimpleNamespace(id=run_id, user_id=test_user.id)
            )
            empty_session = SimpleNamespace(
                session=SimpleNamespace(id="pytest-nothing-here", user_id=test_user.id)
            )
            async with maker() as session:
                invented = await letter_tools._load_brief(
                    session, "brief_12345", context
                )
                by_id = await letter_tools._load_brief(
                    session, "pytestolderbrief", context
                )
                nothing = await letter_tools._load_brief(
                    session, "brief_12345", empty_session
                )
                await session.execute(delete(Letter).where(Letter.session_id == run_id))
                await session.commit()
            return invented.id, by_id.id, nothing
        finally:
            await engine.dispose()

    invented, by_id, nothing = run(main())
    assert invented == "pytestnewerbrief"
    assert by_id == "pytestolderbrief"
    assert nothing is None


def test_writer_request_carries_the_date_and_the_signer():
    text = build_writer_request(
        title="Event Permission Request",
        description="Hackathon permission",
        letter_type_id="event_permission_request",
        user_facts='{"venue": "Kalam Auditorium"}',
        approval_chain="Step 1: Principal — Review (Hitesh Edwin)",
        style_references="",
        sender_name="Nithin",
        sender_organization="Computer Science Club",
        today=datetime(2026, 10, 16),
    )

    assert "Today's date: 16 October 2026" in text
    assert "Sender (who signs this letter): Nithin — Computer Science Club" in text
    assert "Hitesh Edwin" in text
    assert "Kalam Auditorium" in text


def test_writer_request_survives_an_unknown_signer():
    """An unfilled organisation must not leave a dangling em-dash line."""
    text = build_writer_request(
        title="T",
        description="D",
        letter_type_id="event_permission_request",
        user_facts="",
        approval_chain="",
        style_references="",
        sender_name="Nithin",
    )

    assert "Sender (who signs this letter): Nithin\n" in text


def _validation_events(letter):
    async def collect():
        context = SimpleNamespace(session=SimpleNamespace(state={"letter": letter}))
        checker = LetterValidationChecker(name="letter_validation_checker")
        return [event async for event in checker._run_async_impl(context)]

    return run(collect())


def test_complete_letter_passes():
    events = _validation_events(
        "Subject: Permission\nRespected Sir,\nBody.\nSincerely,\nNithin"
    )
    assert events[0].actions.escalate is True


def test_placeholders_are_sent_back_for_a_retry():
    events = _validation_events(
        "Subject: Permission\nRespected [Recipient's Name],\n[Sender Address]\nSincerely"
    )
    assert events[0].actions.escalate is not True
    assert "placeholder" in events[0].content.parts[0].text
