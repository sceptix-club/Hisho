import os
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
