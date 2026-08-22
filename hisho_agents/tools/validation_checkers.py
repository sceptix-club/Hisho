from collections.abc import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part


class LetterValidationChecker(BaseAgent):
    async def _run_async_impl(
        self, context: InvocationContext
    ) -> AsyncGenerator[Event, None]:

        letter = context.session.state.get("letter", "")

        required_sections = ["Subject", "Respected", "Sincerely"]
        missing = [s for s in required_sections if s not in letter]

        if not missing:
            yield Event(
                author=self.name,
                content=Content(
                    parts=[Part(text="Validation successful. All sections present.")]
                ),
                actions=EventActions(escalate=True),
            )
        else:
            feedback = f"Missing sections: {', '.join(missing)}. Please rewrite the letter including these."
            context.session.state["feedback"] = feedback

            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=feedback)]),
            )


class EmailValidationChecker(BaseAgent):
    async def _run_async_impl(
        self, context: InvocationContext
    ) -> AsyncGenerator[Event, None]:

        email = context.session.state.get("email", "")

        required_sections = ["Subject", "Dear", "Regards"]
        missing = [s for s in required_sections if s not in email]

        if not missing:
            yield Event(
                author=self.name,
                content=Content(
                    parts=[Part(text="Validation successful. All sections present.")]
                ),
                actions=EventActions(escalate=True),
            )
        else:
            feedback = f"Missing sections: {', '.join(missing)}. Please rewrite the email including these."
            context.session.state["feedback"] = feedback

            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=feedback)]),
            )
