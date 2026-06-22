from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from config import config
from google.adk.tools import FunctionTool
from hisho_agents.tools.letter_tools import analyze_letters, save_letter_to_file
from hisho_agents.prompts.test_docs_prompt import LETTER_AGENT_INSTRUCTION
from hisho_agents.prompts.email_agent import EMAIL_AGENT_INSTRUCTION
from hisho_agents.prompts.root_prompt import ROOT_AGENT_INSTRUCTION
from hisho_agents.sub_agents.drafting.content_writer import robust_content_writer
from hisho_agents.sub_agents.drafting.email_writer import robust_email_writer
from hisho_agents.sub_agents.workflow.approval_router import approval_router_agent
from hisho_agents.tools.docs import (
    get_google_document,
    create_google_document,
    edit_google_document,
)


interactive_letter_agent = Agent(
    name="interactive_letter_agent",
    model=config.worker_model,
    description="The primary Letter agent. It collaborates with the user to write letters.",
    static_instruction=LETTER_AGENT_INSTRUCTION,
    sub_agents=[robust_content_writer],
    tools=[
        AgentTool(approval_router_agent),
        FunctionTool(save_letter_to_file),
        FunctionTool(analyze_letters),
        FunctionTool(get_google_document),
        FunctionTool(create_google_document),
        FunctionTool(edit_google_document),
    ],
    output_key="final_status",
)


interactive_email_agent = Agent(
    name="interactive_email_agent",
    model=config.worker_model,
    description="The primary Email agent. Drafts professional emails and invitations.",
    static_instruction=EMAIL_AGENT_INSTRUCTION,
    sub_agents=[robust_email_writer],
    output_key="final_status",
)


root_agent = Agent(
    name="root_agent",
    model=config.worker_model,
    description=(
        "Orchestrator that routes user requests to the appropriate workflow: "
        "letters and official correspondence -> letter agent; emails and "
        "invitations -> email agent. Uses natural-language routing over sub_agents."
    ),
    static_instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[interactive_letter_agent, interactive_email_agent],
    output_key="final_status",
)