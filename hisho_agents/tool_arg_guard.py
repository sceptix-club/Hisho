"""Coerce tool arguments to the types each tool declared for them.

ADK advertises a JSON schema to the model but enforces it only for parameters
annotated as pydantic models (``FunctionTool._preprocess_args``). A small model
therefore hands a JSON object to a ``str`` parameter, and the failure surfaces
deep inside whichever tool it reached — asyncpg rejecting a dict for a Text
column, or ``types.Part.from_text`` raising inside an AgentTool.

ADK passes the *same* dict object to this callback and then on to the tool
(flows/llm_flows/functions.py: ``function_args``), so normalising it in place
here repairs the call before it is dispatched.

shortcut: relies on that in-place mutation, which ADK does not document as a
contract. If a future ADK copies the args instead, per-tool coercion (see
``letter_tools._as_text``) is what still holds.
"""

import json
import logging
from typing import Any

from google.adk.plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


def _declared_type(tool: Any, param: str) -> str:
    """The JSON-schema type the tool advertised for ``param`` ('' if unknown)."""
    try:
        declaration = tool._get_declaration()
    except Exception:
        return ""
    properties = getattr(
        getattr(declaration, "parameters", None), "properties", None
    )
    schema = (properties or {}).get(param)
    declared = getattr(schema, "type", None)
    return str(getattr(declared, "value", declared) or "").upper()


class ToolArgGuardPlugin(BasePlugin):
    """Rewrites string-typed tool args that the model sent as objects/arrays."""

    def __init__(self, name: str = "tool_arg_guard"):
        super().__init__(name)

    async def before_tool_callback(self, *, tool, tool_args, tool_context):
        for param, value in list(tool_args.items()):
            if isinstance(value, str) or value is None:
                continue
            if _declared_type(tool, param) != "STRING":
                continue
            if isinstance(value, (dict, list)):
                replacement = json.dumps(value, ensure_ascii=False)
            else:
                replacement = str(value)
            logger.info(
                "Coerced %s.%s from %s to a string",
                tool.name,
                param,
                type(value).__name__,
            )
            tool_args[param] = replacement
        return None
