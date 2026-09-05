from google.adk.agents import Agent, LoopAgent
from hisho_agents.tools.validation_checkers import LetterValidationChecker
from hisho_agents.prompts.content_writer import CONTENT_WRITER_INSTRUCTION
from config import config, settings
from google.adk.models import LiteLlm

# Use a dedicated drafting model (qwen2.5:3b is fast and reliable for letter generation).
# Falls back to the main worker model if the dedicated model is unavailable.
try:
    _draft_model = LiteLlm(model="ollama_chat/qwen2.5:3b", api_base=settings.ollama_base_url)
except Exception:
    _draft_model = config.worker_model

content_writer = Agent(
    model=_draft_model,
    name="content_writer",
    description="Generates a structured letter.",
    static_instruction=CONTENT_WRITER_INSTRUCTION,
    output_key="letter",
)

robust_content_writer = LoopAgent(
    name="robust_content_writer",
    description="A robust letter generator that retries until format is correct.",
    sub_agents=[
        content_writer,
        LetterValidationChecker(name="letter_validation_checker"),
    ],
    max_iterations=2,
)
