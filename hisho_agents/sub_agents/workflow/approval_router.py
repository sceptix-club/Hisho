from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from config import config
from hisho_agents.tools.db import list_letter_types, get_approval_chain_from_db

APPROVAL_ROUTER_INSTRUCTION = """
You are an approval chain specialist. Your job is to determine the correct letter type
for the user's request and provide the chain of command for approvals.

Workflow:
1. FIRST call `list_letter_types` to see all available letter types and their
   descriptions. The descriptions will help you choose the right type.
2. Based on the user's request and the descriptions, pick the most appropriate
   letter type id.
3. Call `get_approval_chain_from_db` with the chosen letter type id.
4. Present the returned chain to the user and ask for confirmation.
5. If the user confirms or requests changes, handle accordingly.
6. Once the chain is finalized, present it clearly in your response so
   the calling agent can use it in the letter.
"""

approval_router_agent = Agent(
    name="approval_router",
    model=config.worker_model,
    description="Determines the letter type and fetches the approval chain of command.",
    instruction=APPROVAL_ROUTER_INSTRUCTION,
    tools=[
        FunctionTool(list_letter_types),
        FunctionTool(get_approval_chain_from_db),
    ],
    output_key="approval_chain_text",
)
