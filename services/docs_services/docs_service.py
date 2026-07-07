from config import Settings
from services.docs_services.google_client import GoogleUserClient


class GoogleDocsService:
    def __init__(self, settings: Settings, access_token: str, refresh_token: str):
        self._client = GoogleUserClient(settings, access_token, refresh_token)

    def fetch_document(self, document_id: str, include_tabs: bool = False) -> dict:
        return (
            self._client.service.documents()
            .get(documentId=document_id, includeTabsContent=include_tabs)
            .execute()
        )

    @staticmethod
    def extract_text(doc: dict) -> str:
        """Flatten a Docs API document body into plain text."""
        parts: list[str] = []
        for item in doc.get("body", {}).get("content", []):
            for el in item.get("paragraph", {}).get("elements", []):
                parts.append(el.get("textRun", {}).get("content", ""))
        return "".join(parts).strip()


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

    def edit_document(self, document_id: str, requests: list[dict]) -> dict:
        """
        Edits an existing Google Document by applying a list of update requests
        via the batchUpdate API.

        Args:
            document_id: The ID of the document to edit.
            requests: A list of request dicts following the Google Docs API
                      batchUpdate format. Supported request types include:

                      - insertText: Insert text at a specific index.
                        {"insertText": {"location": {"index": 1}, "text": "Hello"}}

                      - replaceAllText: Replace all occurrences of a string.
                        {"replaceAllText": {"containsText": {"text": "old", "matchCase": True}, "replaceText": "new"}}

                      - deleteContentRange: Delete content between two indices.
                        {"deleteContentRange": {"range": {"startIndex": 10, "endIndex": 20}}}

                      - insertTable: Insert a table at a given index.
                        {"insertTable": {"rows": 3, "columns": 3, "location": {"index": 1}}}

        Returns:
            A dictionary with the batchUpdate response on success,
            or an error dictionary on failure.
        """
        if not requests:
            return {"error": "No update requests provided."}

        try:
            response = self._client.service.documents().batchUpdate(
                documentId=document_id,
                body={"requests": requests},
            ).execute()
            return {
                "document_id": document_id,
                "replies": response.get("replies", []),
            }
        except Exception as e:
            return {"error": f"Failed to edit document: {str(e)}"}