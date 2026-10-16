"""The model sometimes sends an object where a tool declared a string.

ADK validates only pydantic-model parameters, so the object reaches the tool
and blows up somewhere unrelated to the actual mistake. The guard rewrites it
in flight. It must not touch arguments that really are objects.
"""

import asyncio
import json
from types import SimpleNamespace

from google.adk.tools import FunctionTool
from google.adk.tools.agent_tool import AgentTool

from hisho_agents.sub_agents.workflow.approval_router import approval_router_agent
from hisho_agents.tool_arg_guard import ToolArgGuardPlugin, _declared_type


def _takes_an_object(payload: dict) -> str:
    """Accepts a JSON object on purpose.

    Args:
        payload: A structured payload.
    """
    return "ok"


def _guard():
    return ToolArgGuardPlugin()


def _run(tool, args):
    asyncio.run(
        _guard().before_tool_callback(
            tool=tool,
            tool_args=args,
            tool_context=SimpleNamespace(agent_name="a"),
        )
    )
    return args


def test_declared_type_reads_the_advertised_schema():
    tool = AgentTool(approval_router_agent)
    assert _declared_type(tool, "request") == "STRING"
    assert _declared_type(tool, "nope") == ""


def test_agent_tool_request_sent_as_an_object_is_repaired():
    """This is the crash: AgentTool does types.Part.from_text(args['request'])."""
    args = {
        "request": {"type": "Permission request", "event": "Rain Of Code"}
    }
    repaired = _run(AgentTool(approval_router_agent), args)

    assert isinstance(repaired["request"], str)
    assert json.loads(repaired["request"])["event"] == "Rain Of Code"


def test_a_real_string_is_left_alone():
    args = {"request": "Permission request for a hackathon"}
    assert _run(AgentTool(approval_router_agent), args) == args


def test_an_object_typed_parameter_is_not_coerced():
    tool = FunctionTool(_takes_an_object)
    args = {"payload": {"a": 1}}
    assert _run(tool, args)["payload"] == {"a": 1}
