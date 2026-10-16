"""Persist every LLM and tool call the agents make into ``ai_call_logs``.

Registered on the Runner in main.py. ADK forwards the parent's plugin list into
the child Runner that ``robust_content_writer`` builds (letter_tools.py), so the
writer/validator loop is logged as well, not just the top-level chat.

One row per event: a call is a ``model_request`` row followed by a
``model_response`` row carrying the same ``invocation_id`` and ``agent``.

Writes are best-effort on purpose — a debugging aid must never break a chat.

The plugin deliberately does not override ``close()``: ``Runner.close()`` closes
plugins, and the child Runner in ``robust_content_writer`` closes after every
draft, which would silently end logging for the rest of the session.

shortcut: rows are never pruned — ``ai_call_logs`` grows without bound. Delete
old rows (or add a retention job) once the volume matters.
"""

import logging
from typing import Any, Optional

from google.adk.plugins.base_plugin import BasePlugin

from db.models import AiCallLog
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


def _jsonable(value: Any) -> Any:
    """Coerce genai/pydantic objects and containers into JSON-safe values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return _jsonable(dump(mode="json", exclude_none=True))
        except Exception:
            pass
    return str(value)


def _split_text(content) -> tuple[str, str]:
    """Return (text, thoughts); thinking must not be mistaken for the reply."""
    text: list[str] = []
    thoughts: list[str] = []
    for part in (content.parts or []) if content else []:
        chunk = getattr(part, "text", None)
        if not chunk:
            continue
        (thoughts if getattr(part, "thought", False) else text).append(chunk)
    return "".join(text), "".join(thoughts)


def _function_calls(content) -> list[dict]:
    calls: list[dict] = []
    for part in (content.parts or []) if content else []:
        call = getattr(part, "function_call", None)
        if call:
            calls.append({"name": call.name, "args": _jsonable(call.args)})
    return calls


def _session_id(context) -> Optional[str]:
    try:
        return context.session.id
    except Exception:
        return None


class AiCallLogPlugin(BasePlugin):
    """Writes one ``ai_call_logs`` row per model or tool event."""

    def __init__(self, name: str = "ai_call_log"):
        super().__init__(name)

    async def _record(
        self,
        kind: str,
        *,
        context: Any = None,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        tool_name: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> None:
        try:
            async with AsyncSessionLocal() as session:
                session.add(
                    AiCallLog(
                        kind=kind,
                        invocation_id=getattr(context, "invocation_id", None),
                        session_id=_session_id(context),
                        user_id=getattr(context, "user_id", None),
                        agent=agent or getattr(context, "agent_name", None),
                        model=model,
                        tool_name=tool_name,
                        payload=payload or {},
                    )
                )
                await session.commit()
        except Exception as exc:  # never let logging break a chat
            logger.warning("ai_call_logs write failed (%s): %s", kind, exc)

    # --- model ---------------------------------------------------------------
    async def before_model_callback(self, *, callback_context, llm_request):
        await self._record(
            "model_request",
            context=callback_context,
            model=llm_request.model,
            payload={
                "system_instruction": _jsonable(
                    getattr(llm_request.config, "system_instruction", None)
                ),
                "contents": _jsonable(llm_request.contents),
                "tools": sorted((llm_request.tools_dict or {}).keys()),
            },
        )

    async def after_model_callback(self, *, callback_context, llm_response):
        # Streaming yields one LlmResponse per chunk plus a final aggregate;
        # logging chunks would write hundreds of near-identical, growing rows.
        if llm_response.partial:
            return None
        text, thoughts = _split_text(llm_response.content)
        await self._record(
            "model_response",
            context=callback_context,
            model=llm_response.model_version,
            payload={
                "text": text,
                "thoughts": thoughts,
                "function_calls": _function_calls(llm_response.content),
                "usage": _jsonable(llm_response.usage_metadata),
                "turn_complete": llm_response.turn_complete,
                "error_code": llm_response.error_code,
                "error_message": llm_response.error_message,
            },
        )

    async def on_model_error_callback(self, *, callback_context, llm_request, error):
        await self._record(
            "model_error",
            context=callback_context,
            model=llm_request.model,
            payload={"error": str(error)},
        )

    # --- tools ---------------------------------------------------------------
    async def before_tool_callback(self, *, tool, tool_args, tool_context):
        await self._record(
            "tool_request",
            context=tool_context,
            tool_name=tool.name,
            payload={"args": _jsonable(tool_args)},
        )

    async def after_tool_callback(self, *, tool, tool_args, tool_context, result):
        await self._record(
            "tool_result",
            context=tool_context,
            tool_name=tool.name,
            payload={"args": _jsonable(tool_args), "result": _jsonable(result)},
        )

    async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error):
        await self._record(
            "tool_error",
            context=tool_context,
            tool_name=tool.name,
            payload={"args": _jsonable(tool_args), "error": str(error)},
        )
