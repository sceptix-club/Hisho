import glob
import os
import re
import asyncio
import logging
import uuid

from google.adk.tools import ToolContext
from google.genai import types
from sqlalchemy import select

from db.models import Letter
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def analyze_letters(directory: str) -> dict:
    """Analyze the letters in the directory, understand the format and strictly adhere to it."""

    def _sync_analyze():
        files = glob.glob(os.path.join(directory, "**"), recursive=True)
        allowed_extensions = {".txt", ".md"}
        context = ""

        for file in files:
            if not os.path.isfile(file):
                continue

            _, ext = os.path.splitext(file)
            if ext.lower() not in allowed_extensions:
                continue

            try:
                with open(file, encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(file, encoding="latin-1") as f:
                    content = f.read()

            context += f"\n--- LETTER: {file} ---\n"
            context += content.strip() + "\n"
        return context

    context = await asyncio.to_thread(_sync_analyze)
    return {"letter_context": context}


def save_letter_to_file(letter: str, filename: str) -> str:
    """
    Saves the letter text to a file.
    This agent handles the physical saving of the letter and terminates the session.
    """
    with open(filename, "w", encoding="utf-8") as f:
        f.write(letter)
    return f"Successfully saved letter to {filename}."


def _resolve_tool_user_id(tool_context: ToolContext | None) -> str:
    if tool_context is None:
        return "default"
    try:
        return tool_context.session.user_id or "default"
    except Exception:
        return "default"


def _resolve_tool_session_id(tool_context: ToolContext | None) -> str | None:
    if tool_context is None:
        return None
    try:
        return tool_context.session.id
    except Exception:
        return None


async def create_letter_brief(
    title: str,
    description: str,
    letter_type_id: str,
    user_facts: str = "",
    approval_chain: str = "",
    style_references: str = "",
    tool_context: ToolContext | None = None,
) -> str:
    """Persist a letter brief in the DB before invoking the content writer.

    Call this AFTER gathering all facts, the approval chain (from
    approval_router), and style references (from find_similar_letters),
    but BEFORE calling robust_content_writer.  It creates a Letter row
    with status="pending" so the request survives even if writing fails.

    Args:
        title: Short title for the letter (e.g. "Leave letter for fever - 6 March 2026").
        description: One-line description of the request.
        letter_type_id: Letter type id chosen via approval_router (e.g. "leave_letter").
        user_facts: All facts gathered from the conversation (purpose, names,
            dates, addresses, etc.).
        approval_chain: Resolved approval chain text from approval_router.
        style_references: Style examples from find_similar_letters.
        tool_context: Injected automatically by ADK — provides user_id/session_id.

    Returns:
        The new letter id (brief id) to pass to robust_content_writer.
    """
    letter_id = uuid.uuid4().hex
    reference_number = f"LT-{letter_id[:8].upper()}"
    user_id = _resolve_tool_user_id(tool_context)
    session_id = _resolve_tool_session_id(tool_context)
    async with AsyncSessionLocal() as session:
        letter = Letter(
            id=letter_id,
            reference_number=reference_number,
            letter_type_id=letter_type_id,
            description=description,
            title=title,
            approved=False,
            content=None,
            user_facts=user_facts,
            approval_chain=approval_chain,
            style_references=style_references,
            status="pending",
            user_id=user_id,
            session_id=session_id,
        )
        session.add(letter)
        await session.commit()
    logger.info("Created letter brief %s (%s) for user %s", letter_id, title, user_id)
    return f"Brief created with id={letter_id} reference={reference_number} status=pending"


async def robust_content_writer(
    brief_id: str,
    tool_context: ToolContext | None = None,
) -> str:
    """Generate the letter for a previously created brief.

    Fetches the Letter brief from the DB by ``brief_id``, runs the
    content writer (with validation loop), stores the resulting letter
    text back on the same Letter row (status=complete), and returns the
    letter text.

    This is the ONLY way to generate letter content — always call
    ``create_letter_brief`` first to obtain a ``brief_id``.

    Args:
        brief_id: The Letter id returned by ``create_letter_brief``.
            If the full return string from that tool is passed (e.g.
            "Brief created with id=abc..."), the id is extracted
            automatically.
        tool_context: Injected automatically by ADK.

    Returns:
        The final, validated letter text (also persisted in the DB).
    """
    # --- 1. Extract raw id if LLM passed the full return string ---
    m = re.search(r"id=([a-f0-9]+)", brief_id)
    if m:
        brief_id = m.group(1)
    brief_id = brief_id.strip()

    # --- 2. Fetch brief from DB ---
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Letter).where(Letter.id == brief_id))
        brief = result.scalar_one_or_none()
        if brief is None:
            return f"Error: no letter brief found with id={brief_id}. Call create_letter_brief first."
        # Snapshot fields while session is open
        title = brief.title
        description = brief.description
        letter_type_id = brief.letter_type_id
        user_facts = brief.user_facts or ""
        approval_chain = brief.approval_chain or ""
        style_references = brief.style_references or ""

    # --- 3. Build a plain natural-language request for the writer ---
    # The content_writer LoopAgent has no tools — it just writes from this text.
    request_parts = [
        f"Title: {title}",
        f"Description: {description}",
        f"Letter type: {letter_type_id}",
    ]
    if user_facts:
        request_parts.append(f"User facts: {user_facts}")
    if approval_chain:
        request_parts.append(f"Approval chain (use for recipient and sign-off order): {approval_chain}")
    if style_references:
        # Truncate to avoid blowing context
        request_parts.append(f"Style references (structure/tone only, do not copy content): {style_references[:3000]}")
    request_parts.append(
        "Write the complete formal letter. Include Subject, Respected, and Sincerely sections. "
        "Dates are day-first: 05/03/26 means 5 March 2026. Use every fact provided."
    )
    request_text = "\n\n".join(request_parts)

    # --- 4. Run the LoopAgent (content_writer + validator) as a child runner ---
    # Lazily import to avoid circular imports (agent.py imports from letter_tools)
    from hisho_agents.sub_agents.drafting.content_writer import robust_content_writer as loop_agent

    try:
        from google.adk.runners import Runner
        from google.adk.sessions.in_memory_session_service import InMemorySessionService
        from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
        from google.adk.tools._forwarding_artifact_service import ForwardingArtifactService
        from google.adk.utils.context_utils import Aclosing
    except ImportError as e:
        logger.error("Failed to import ADK runner components: %s", e)
        return f"Error: internal imports failed ({e})"

    # Determine parent app/user for child runner
    invocation_context = None
    parent_app_name = "hisho"
    parent_user_id = "default"
    plugins = None
    artifact_service = None
    credential_service = None
    if tool_context is not None:
        try:
            invocation_context = tool_context._invocation_context
            if invocation_context:
                parent_app_name = invocation_context.app_name or "hisho"
                parent_user_id = invocation_context.user_id or "default"
                try:
                    plugins = invocation_context.plugin_manager.plugins
                except Exception:
                    plugins = None
                try:
                    credential_service = invocation_context.credential_service
                except Exception:
                    credential_service = None
        except Exception:
            pass
        try:
            artifact_service = ForwardingArtifactService(tool_context)
        except Exception:
            artifact_service = None

    runner = Runner(
        app_name=parent_app_name,
        agent=loop_agent,
        artifact_service=artifact_service,
        session_service=InMemorySessionService(),
        memory_service=InMemoryMemoryService(),
        credential_service=credential_service,
        plugins=plugins,
    )

    # Copy parent session state (if any) into child, excluding internal keys
    state_dict: dict = {}
    if tool_context is not None:
        try:
            state_dict = {
                k: v
                for k, v in tool_context.state.to_dict().items()
                if not k.startswith("_adk")
            }
        except Exception:
            state_dict = {}

    session_obj = await runner.session_service.create_session(
        app_name=parent_app_name,
        user_id=parent_user_id,
        state=state_dict,
    )

    content = types.Content(role="user", parts=[types.Part.from_text(text=request_text)])
    last_content = None
    letter_from_state = ""

    async def _run_writer():
        nonlocal last_content, letter_from_state
        async with Aclosing(
            runner.run_async(
                user_id=session_obj.user_id,
                session_id=session_obj.id,
                new_message=content,
            )
        ) as agen:
            async for event in agen:
                # Capture letter from state_delta (output_key="letter") — this is the real letter,
                # not the validator's "Validation successful" message which appears as last_content.
                if event.actions and event.actions.state_delta:
                    if "letter" in event.actions.state_delta:
                        letter_from_state = event.actions.state_delta["letter"] or ""
                    if tool_context is not None:
                        try:
                            tool_context.state.update(event.actions.state_delta)
                        except Exception:
                            pass
                if event.content:
                    last_content = event.content

    try:
        # Guard against slow LLM — fail fast rather than hanging the chat
        await asyncio.wait_for(_run_writer(), timeout=90)
    except asyncio.TimeoutError:
        logger.warning("robust_content_writer timed out for brief %s after 90s", brief_id)
        try:
            await runner.close()
        except Exception:
            pass
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Letter).where(Letter.id == brief_id))
            b = result.scalar_one_or_none()
            if b and b.status == "pending":
                b.status = "failed"
                await session.commit()
        return "Error: the writer timed out. Please retry."
    finally:
        try:
            await runner.close()
        except Exception:
            pass

    # --- 5. Extract letter text ---
    # Prefer the letter captured from state_delta; last_content may be the validator's
    # "Validation successful" message which is not the letter.
    letter_text = letter_from_state.strip() if letter_from_state else ""
    if not letter_text and last_content and last_content.parts:
        candidate = "\n".join(
            p.text for p in last_content.parts if getattr(p, "text", None) and not getattr(p, "thought", False)
        ).strip()
        # Guard against validator message being mistaken for the letter
        if candidate and "Validation successful" not in candidate:
            letter_text = candidate
        elif candidate:
            # last_content was validator — try to recover from child session or parent state
            try:
                child_session = await runner.session_service.get_session(
                    app_name=parent_app_name, user_id=parent_user_id, session_id=session_obj.id
                )
                if child_session and child_session.state:
                    letter_text = child_session.state.get("letter", "") or ""
            except Exception:
                pass
            if not letter_text and tool_context is not None:
                try:
                    letter_text = tool_context.state.get("letter", "") or ""
                except Exception:
                    pass
    # Final fallback: parent state (when tool_context was provided)
    if not letter_text and tool_context is not None:
        try:
            letter_text = tool_context.state.get("letter", "") or ""
        except Exception:
            pass
    if not letter_text:
        # Mark failed and return error
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Letter).where(Letter.id == brief_id))
            b = result.scalar_one_or_none()
            if b:
                b.status = "failed"
                await session.commit()
        return "Error: the writer produced no content. Please retry."

    # --- 6. Persist letter text on the same Letter row ---
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Letter).where(Letter.id == brief_id))
        b = result.scalar_one_or_none()
        if b is not None:
            b.content = letter_text
            b.status = "complete"
            await session.commit()
            logger.info("Letter brief %s completed (%d chars)", brief_id, len(letter_text))
        else:
            logger.warning("Brief %s disappeared before completion", brief_id)

    return letter_text
