import asyncio
import logging
from typing import Optional

from google.adk.tools import ToolContext
from sqlalchemy import select

from config import settings
from db.models import User
from db.session import AsyncSessionLocal
from services.docs_services.docs_service import GoogleDocsService
from hisho_agents.tools.db import remember_letter

logger = logging.getLogger(__name__)


async def _load_user_tokens(user_id: str) -> tuple[Optional[str], Optional[str]]:
    """Load the user's Google OAuth tokens from the database."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
    if user is None:
        return None, None
    return user.google_access_token, user.google_refresh_token


async def _persist_access_token(user_id: str, access_token: str) -> None:
    """Best-effort: store a refreshed Google access token back on the user row."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user and user.google_access_token != access_token:
                user.google_access_token = access_token
                await session.commit()
    except Exception as e:  # never block a letter save over this
        logger.warning("Could not persist refreshed Google token: %s", e)


def _resolve_user_id(tool_context: Optional[ToolContext]) -> Optional[str]:
    if tool_context is None:
        return None
    try:
        return tool_context.session.user_id
    except Exception:
        return None


async def _get_service(user_id: Optional[str]):
    """Return (GoogleDocsService, None) or (None, error_message)."""
    if not user_id:
        return None, (
            "Failure: user identity was not available for this request. "
            "Make sure you are logged in."
        )
    access_token, refresh_token = await _load_user_tokens(user_id)
    if not access_token or not refresh_token:
        return (
            None,
            "Failure: your Google account is not connected. Please log in with "
            "Google (with Drive access) before saving letters to Google Docs.",
        )
    try:
        return GoogleDocsService(settings, access_token, refresh_token), None
    except Exception as e:  # network/auth failure building the client must not crash the chat
        logger.warning("Could not build Google client: %s", e)
        return (
            None,
            "Failure: could not connect to Google to build the Docs client "
            f"({type(e).__name__}). Check your network connection and try again.",
        )


async def _after(service: Optional[GoogleDocsService], user_id: Optional[str]) -> None:
    if service is None or not user_id:
        return
    try:
        await _persist_access_token(user_id, service._client.creds.token)
    except Exception as e:
        logger.warning("Token refresh persistence skipped: %s", e)


def _doc_end_index(doc: dict) -> int:
    """Index just past the last character of the document body."""
    content = doc.get("body", {}).get("content", [])
    if not content:
        return 1
    return content[-1].get("endIndex", 1)


async def get_google_document(
    document_id: str, tool_context: ToolContext = None
) -> dict:
    """Fetches a Google Document by its ID using the user's Google account."""
    user_id = _resolve_user_id(tool_context)
    service, err = await _get_service(user_id)
    if err:
        return {"error": err}
    try:
        return service.fetch_document(document_id)
    except Exception as e:
        logger.warning("get_google_document failed: %s", e)
        return {
            "error": f"Failure: could not read the Google document ({type(e).__name__}). "
            "Check your connection and try again."
        }
    finally:
        await _after(service, user_id)


async def create_google_document(
    title: str, content: str, tool_context: ToolContext = None
) -> dict:
    """Creates a new Google Document in the user's Drive with the given content."""
    user_id = _resolve_user_id(tool_context)
    service, err = await _get_service(user_id)
    if err:
        return {"error": err}
    try:
        doc = await asyncio.to_thread(service.create_document, title, content)
        try:
            await remember_letter(title, content, source_doc_id=doc.get("document_id"))
        except Exception as e:
            logger.warning("Could not store letter in memory: %s", e)
        return doc
    except Exception as e:
        logger.warning("create_google_document failed: %s", e)
        return {
            "error": f"Failure: could not create the Google document ({type(e).__name__}). "
            "Check your connection and try again."
        }
    finally:
        await _after(service, user_id)


async def edit_google_document(
    document_id: str, requests: list[dict], tool_context: ToolContext = None
) -> dict:
    """Edits an existing Google Document in the user's Drive via batchUpdate."""
    user_id = _resolve_user_id(tool_context)
    service, err = await _get_service(user_id)
    if err:
        return {"error": err}
    try:
        return service.edit_document(document_id, requests)
    except Exception as e:
        logger.warning("edit_google_document failed: %s", e)
        return {
            "error": f"Failure: could not edit the Google document ({type(e).__name__}). "
            "Check your connection and try again."
        }
    finally:
        await _after(service, user_id)


async def sync_letter_to_google_docs(
    letter_content: str,
    title: str,
    document_id: str | None = None,
    tool_context: ToolContext = None,
) -> dict:
    """Push the current letter to the user's Google Drive on command.

    Creates a new document the first time it is called for a chat, and
    overwrites the same document on later calls (so re-syncing edits the
    existing doc instead of creating duplicates). The document id is remembered
    in the session so follow-up syncs and edits keep hitting the same doc.

    Args:
        letter_content: The full letter text to write into the document.
        title: The document title.
        document_id: Optional existing document id to overwrite. If omitted,
            the id remembered in the session is used; otherwise a new doc is
            created.

    Returns:
        A dict with document_id, url and title, or an error dict.
    """
    user_id = _resolve_user_id(tool_context)
    service, err = await _get_service(user_id)
    if err:
        return {"error": err}

    target_id = document_id
    if not target_id and tool_context is not None:
        try:
            target_id = tool_context.session.state.get("google_doc_id")
        except Exception:
            target_id = None

    try:
        if target_id:
            doc = await asyncio.to_thread(service.fetch_document, target_id)
            end_index = _doc_end_index(doc)
            requests = []
            if end_index > 1:
                requests.append(
                    {
                        "deleteContentRange": {
                            "range": {"startIndex": 1, "endIndex": end_index}
                        }
                    }
                )
            requests.append(
                {"insertText": {"location": {"index": 1}, "text": letter_content}}
            )
            await asyncio.to_thread(service.edit_document, target_id, requests)
            final_id = target_id
        else:
            created = await asyncio.to_thread(
                service.create_document, title, letter_content
            )
            final_id = created.get("document_id")

        if tool_context is not None and final_id:
            try:
                tool_context.state["google_doc_id"] = final_id
            except Exception as e:
                logger.warning("Could not store doc id in session state: %s", e)

        try:
            await remember_letter(title, letter_content, source_doc_id=final_id)
        except Exception as e:
            logger.warning("Could not store letter in memory: %s", e)

        return {
            "document_id": final_id,
            "url": f"https://docs.google.com/document/d/{final_id}/edit",
            "title": title,
        }
    except Exception as e:
        logger.warning("sync_letter_to_google_docs failed: %s", e)
        return {
            "error": f"Failure: could not sync to Google Docs ({type(e).__name__}). "
            "Check your connection and try again."
        }
    finally:
        await _after(service, user_id)
