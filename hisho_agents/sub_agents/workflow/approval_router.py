from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from config import config
from hisho_agents.tools.db import list_letter_types, get_approval_chain_from_db

APPROVAL_ROUTER_INSTRUCTION = """
You are an approval chain specialist. Your job is to determine the correct letter type
for the request you are given and provide the chain of command for approvals.

You are called as a HELPER by another agent, not directly by the end user. Do NOT ask
the end user any questions - just resolve the request and return the chain.

Workflow:
1. FIRST call `list_letter_types` to see all available letter types and their
   descriptions. The descriptions will help you choose the right type.
2. Based on the request you were given and the descriptions, pick the most appropriate
   letter type id.
3. Call `get_approval_chain_from_db` with the chosen letter type id.
4. Return the chain clearly and directly in your response: state the chosen letter type
   id and list the officials (with names and roles, in order) from the chain. The calling
   agent will use the chain to set the letter's recipient and sign-off order.
5. Do NOT ask for confirmation and do NOT ask the user any questions - just return the
   result so the calling agent can continue drafting the letter.
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
