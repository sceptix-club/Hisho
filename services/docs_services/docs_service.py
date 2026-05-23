from config import Settings
from services.docs_services.google_client import GoogleUserClient


class GoogleDocsService:
    def __init__(self, settings: Settings, access_token: str, refresh_token: str):
        self._client = GoogleUserClient(settings, access_token, refresh_token)

    def fetch_document(self, document_id: str) -> dict:
        return self._client.service.documents().get(documentId=document_id).execute()

    def create_document(self, title: str, content: str) -> dict:
        file = self._client.drive_service.files().create(
            body={"name": title, "mimeType": "application/vnd.google-apps.document"}
        ).execute()

        document_id = file.get("id")

        self._client.service.documents().batchUpdate(
            documentId=document_id,
            body={
                "requests": [
                    {
                        "insertText": {
                            "location": {"index": 1},
                            "text": content
                        }
                    }
                ]
            }
        ).execute()

        return {"document_id": document_id, "title": title}