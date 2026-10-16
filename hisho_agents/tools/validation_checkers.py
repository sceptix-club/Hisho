from collections.abc import AsyncGenerator
import re

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part


class LetterValidationChecker(BaseAgent):
    async def _run_async_impl(
        self, context: InvocationContext
    ) -> AsyncGenerator[Event, None]:

        letter = context.session.state.get("letter", "")

        problems = [
            f"missing section: {s}"
            for s in ("Subject", "Respected", "Sincerely")
            if s not in letter
        ]

        # A placeholder means the writer had no data and invented a shell. Send
        # it back for one retry rather than shipping a letter full of [Brackets].
        placeholders = sorted(set(re.findall(r"\[[^\]]{1,60}\]", letter)))
        if placeholders:
            problems.append(
                "unfilled placeholders — use the supplied details, or drop those "
                f"lines: {', '.join(placeholders[:5])}"
            )

        if not problems:
            yield Event(
                author=self.name,
                content=Content(
                    parts=[Part(text="Validation successful. All sections present.")]
                ),
                actions=EventActions(escalate=True),
            )
        else:
            feedback = "The letter needs fixing: " + "; ".join(problems)
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
