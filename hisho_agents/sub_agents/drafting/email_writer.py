from google.adk.agents import Agent, LoopAgent
from hisho_agents.tools.validation_checkers import EmailValidationChecker
from hisho_agents.prompts.email_writer import EMAIL_WRITER_INSTRUCTION
from config import config

email_writer = Agent(
	model=config.worker_model,
	name="email_writer",
	description="Generates professional emails.",
	static_instruction=EMAIL_WRITER_INSTRUCTION,
	output_key="email",
)

robust_email_writer = LoopAgent(
	name="robust_email_writer",
	description="Retries until the email format is correct.",
	sub_agents=[
		email_writer,
		EmailValidationChecker(name="email_validation_checker"),
	],
	max_iterations=2,
)
