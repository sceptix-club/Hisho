from google.adk.agents import Agent, LoopAgent
from hisho_agents.tools.validation_checkers import LetterValidationChecker
from hisho_agents.prompts.content_writer import CONTENT_WRITER_INSTRUCTION
from config import config

content_writer = Agent(
    model=config.worker_model,
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
