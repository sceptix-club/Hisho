from config import Settings
from services.docs_services.google_client import GoogleUserClient


class GoogleDocsService:
    def __init__(self, settings: Settings, access_token: str, refresh_token: str):
        self._client = GoogleUserClient(settings, access_token, refresh_token)

    def fetch_document(self, document_id: str) -> dict:
        return self._client.service.documents().get(documentId=document_id).execute()