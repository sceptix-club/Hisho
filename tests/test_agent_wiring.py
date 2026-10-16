"""Regression: leaf workers must not be offered `transfer_to_agent`.

ADK hands every agent a transfer tool by default. For a leaf worker that is an
escape hatch back to the parent, and a small local model mid-pipeline will take
it: the letter agent bounced to root_agent, got re-dispatched, and looped until
its iteration budget ran out — returning no text, so the UI showed
"No response. Please retry." even though the letter had been written to the DB.
"""

import asyncio

from google.adk.agents.invocation_context import InvocationContext
from google.adk.flows.llm_flows.agent_transfer import request_processor
from google.adk.models.llm_request import LlmRequest
from google.adk.sessions import InMemorySessionService
from google.genai import types

from hisho_agents.agent import (
    interactive_email_agent,
    interactive_letter_agent,
    root_agent,
)


def run(coro):
    return asyncio.run(coro)


def _transfer_targets(req):
    """The agent_name enum of the transfer tool, or None if it isn't offered."""
    for tool in req.config.tools or []:
        decls = (
            tool.get("function_declarations")
            if isinstance(tool, dict)
            else getattr(tool, "function_declarations", None)
        )
        for decl in decls or []:
            if decl.name == "transfer_to_agent":
                prop = decl.parameters.properties.get("agent_name")
                return list(prop.enum) if prop else []
    return None


async def _targets_for(agent):
    svc = InMemorySessionService()
    session = await svc.create_session(app_name="t", user_id="u")
    ctx = InvocationContext(
        invocation_id="i",
        branch="b",
        agent=agent,
        session=session,
        session_service=svc,
        user_content=types.Content(role="user", parts=[types.Part(text="hello")]),
    )
    req = LlmRequest()
    async for _ in request_processor.run_async(ctx, req):
        pass
    return _transfer_targets(req)


def test_leaf_workers_cannot_transfer():
    for agent in (interactive_letter_agent, interactive_email_agent):
        assert run(_targets_for(agent)) is None, (
            f"{agent.name} is a leaf worker but is offered transfer_to_agent; "
            "a confused model will bounce to root_agent and loop"
        )


def test_root_agent_still_routes():
    assert set(run(_targets_for(root_agent)) or []) == {
        "interactive_letter_agent",
        "interactive_email_agent",
    }
