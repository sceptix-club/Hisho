from services.docs_services.docs_service import GoogleDocsService
from config import settings

def get_google_document(document_id: str) -> dict:
    """
    Fetches a Google Document by its ID using GoogleDocsService.
    
    Args:
        document_id: The ID of the Google Document to fetch.

        
    Returns:
        A dictionary containing the document data.
    """
    access_token = settings.test_access_token
    if not access_token:
        return {"error": "Failure: No access token found"}
        
    refresh_token = settings.test_refresh_token
    if not refresh_token:
        return {"error": "Failure: No refresh token found"}
    
    docs_service = GoogleDocsService(settings, access_token, refresh_token)
    return docs_service.fetch_document(document_id)

def create_google_document(title: str, content: str) -> dict:
    """
    Creates a new Google Document with the specified title and content using GoogleDocsService.
    
    Args:
        title: The title of the new document.
        content: The initial content to insert into the document.
        
    Returns:
        A dictionary containing the document data (e.g., document_id and title).
    """
    access_token = settings.test_access_token
    if not access_token:
        return {"error": "Failure: No access token found"}
        
    refresh_token = settings.test_refresh_token
    if not refresh_token:
        return {"error": "Failure: No refresh token found"}
    
    docs_service = GoogleDocsService(settings, access_token, refresh_token)
    return docs_service.create_document(title, content)

def edit_google_document(document_id: str, requests: list[dict]) -> dict:
    """
    Edits an existing Google Document by applying a list of update requests.

    Args:
        document_id: The ID of the Google Document to edit.
        requests: A list of update request dicts in the Google Docs API batchUpdate format.
                  Supported request types include:

                  - insertText: Insert text at a specific index.
                    Example: {"insertText": {"location": {"index": 1}, "text": "Hello World"}}

                  - replaceAllText: Replace all occurrences of a string in the document.
                    Example: {"replaceAllText": {"containsText": {"text": "{{placeholder}}", "matchCase": True}, "replaceText": "Actual Value"}}

                  - deleteContentRange: Delete content between two indices.
                    Example: {"deleteContentRange": {"range": {"startIndex": 10, "endIndex": 20}}}

                  - insertTable: Insert a table at a given index.
                    Example: {"insertTable": {"rows": 3, "columns": 3, "location": {"index": 1}}}

                  Multiple requests can be combined in a single call; they execute atomically.

    Returns:
        A dictionary with the document_id and batchUpdate replies on success,
        or an error dictionary on failure.
    """
    access_token = settings.test_access_token
    if not access_token:
        return {"error": "Failure: No access token found"}

    refresh_token = settings.test_refresh_token
    if not refresh_token:
        return {"error": "Failure: No refresh token found"}

    docs_service = GoogleDocsService(settings, access_token, refresh_token)
    return docs_service.edit_document(document_id, requests)
