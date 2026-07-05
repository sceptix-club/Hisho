import logging
import uuid
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from config import settings
from hisho_agents.agent import root_agent
from api.routes.letter_types import router as letter_types_router
from api.routes.letters import router as letters_router
from api.routes.officials import router as officials_router
from api.schemas.hisho import ChatRequest
import json


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async_db_url = settings.database_url.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )
    app.state.db_session_service = DatabaseSessionService(db_url=async_db_url)
    app.state.runner = Runner(
        app_name="hisho",
        agent=root_agent,
        session_service=app.state.db_session_service,
        auto_create_session=True,
    )
    logger.info("Runner and DatabaseSessionService initialized")
    yield
    await app.state.db_session_service.close()
    logger.info("DatabaseSessionService closed")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(letters_router)
app.include_router(officials_router)
app.include_router(letter_types_router)


@app.get("/")
async def root():
    return {"message": "API running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(query: str, session_id: str | None = None, user_id: str = "default"):
    runner: Runner = app.state.runner
    user_message = types.Content(role="user", parts=[types.Part(text=query)])
    sid = session_id or uuid.uuid4().hex
    final_response_text = None
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=sid,
            new_message=user_message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_response_text = event.content.parts[-1].text
        if final_response_text is None:
            raise HTTPException(
                status_code=500,
                detail="Agent did not produce a final response.",
            )
        return {"response": final_response_text, "session_id": sid}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error during chat: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


def _sse_event(data: dict) -> str:
    return "data: " + json.dumps(data) + "\n\n"


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    runner: Runner = app.state.runner
    sid = req.session_id or uuid.uuid4().hex
    user_message = types.Content(role="user", parts=[types.Part(text=req.query)])

    async def event_stream():
        async for event in runner.run_async(
            user_id=req.user_id,
            session_id=sid,
            new_message=user_message,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            if event.actions and event.actions.transfer_to_agent:
                yield _sse_event(
                    {
                        "type": "transfer",
                        "agent": event.actions.transfer_to_agent,
                    }
                )

            for call in event.get_function_calls():
                yield _sse_event(
                    {
                        "type": "tool_call",
                        "name": call.name,
                        "args": call.args,
                    }
                )

            for resp in event.get_function_responses():
                yield _sse_event(
                    {
                        "type": "tool_result",
                        "name": resp.name,
                        "result": resp.response,
                    }
                )

            if not event.content or not event.content.parts:
                continue

            is_partial = getattr(event, "partial", False)
            is_final = event.is_final_response()

            for part in event.content.parts:
                text = getattr(part, "text", None)
                if not text:
                    continue

                is_thought = getattr(part, "thought", False)

                if is_thought:
                    yield _sse_event({"type": "thought", "text": text})
                elif is_partial:
                    yield _sse_event({"type": "delta", "text": text})
                elif is_final:
                    yield _sse_event({"type": "message", "text": text})

            if is_final:
                yield _sse_event({"type": "done", "session_id": sid})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)
