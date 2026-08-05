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
        """Flatten a Docs API document body into plain text.

        Tables are rendered as 'cell | cell' lines - a shape the drafting
        model can reproduce through the plain-text insertText output path.
        """
        return GoogleDocsService._extract_content(
            doc.get("body", {}).get("content", [])
        ).strip()

    @staticmethod
    def _extract_content(content: list) -> str:
        parts: list[str] = []
        for item in content:
            if "paragraph" in item:
                for el in item["paragraph"].get("elements", []):
                    parts.append(el.get("textRun", {}).get("content", ""))
            elif "table" in item:
                for row in item["table"].get("tableRows", []):
                    cells = [
                        GoogleDocsService._extract_content(
                            cell.get("content", [])
                        ).strip()
                        for cell in row.get("tableCells", [])
                    ]
                    parts.append(" | ".join(cells) + "\n")
            elif "tableOfContents" in item:
                parts.append(
                    GoogleDocsService._extract_content(
                        item["tableOfContents"].get("content", [])
                    )
                )
        return "".join(parts)


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

    def ensure_folder(self, folder_name: str) -> str:
        """Return the ID of a Drive folder with *folder_name*, creating it if absent.

        Searches only for folders owned by the authenticated user that are
        not in the trash.
        """
        query = (
            f"name = '{folder_name}' "
            "and mimeType = 'application/vnd.google-apps.folder' "
            "and trashed = false"
        )
        results = (
            self._client.drive_service.files()
            .list(q=query, spaces="drive", fields="files(id, name)")
            .execute()
        )
        files = results.get("files", [])
        if files:
            return files[0]["id"]

        folder_meta = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = (
            self._client.drive_service.files()
            .create(body=folder_meta, fields="id")
            .execute()
        )
        return folder["id"]

    def copy_document_to_folder(
        self, document_id: str, title: str, folder_id: str
    ) -> dict:
        """Create an exact copy of a Google Doc inside *folder_id* via Drive copy.

        Uses ``files().copy()`` which preserves all formatting, tables,
        styles, headers, footers, etc. — no lossy HTML round-trip.

        Returns:
            ``{"document_id": str, "title": str, "url": str}``
        """
        copy_meta = {"name": title, "parents": [folder_id]}
        copied = (
            self._client.drive_service.files()
            .copy(
                fileId=document_id,
                body=copy_meta,
                fields="id, webViewLink",
            )
            .execute()
        )
        copy_id = copied["id"]
        web_url = copied.get(
            "webViewLink",
            f"https://docs.google.com/document/d/{copy_id}/edit",
        )
        print("Web Url ----> ",web_url)
        return {"document_id": copy_id, "title": title, "url": web_url}

    def apply_template_replacements(
        self, document_id: str, replacements: list[dict],
        tab_id: str | None = None,
    ) -> dict:
        """Apply ``replaceAllText`` requests to turn a document into a template.

        Args:
            document_id: ID of the Google Doc to modify.
            replacements: List of dicts with ``original_text`` and
                ``placeholder`` keys.
            tab_id: Optional tab ID to scope replacements to a specific tab.
                When ``None``, replacements apply to all tabs.

        Returns:
            A summary dict with the document_id, count of replacements
            applied, and the raw batchUpdate replies.
        """
        if not replacements:
            return {
                "document_id": document_id,
                "message": "No replacements to apply",
            }

        requests = []
        for r in replacements:
            req: dict = {
                "replaceAllText": {
                    "containsText": {
                        "text": r["original_text"],
                        "matchCase": True,
                    },
                    "replaceText": r["placeholder"],
                }
            }
            if tab_id:
                req["replaceAllText"]["tabsCriteria"] = {
                    "tabIds": [tab_id],
                }
            requests.append(req)

        response = (
            self._client.service.documents()
            .batchUpdate(
                documentId=document_id, body={"requests": requests}
            )
            .execute()
        )
        return {
            "document_id": document_id,
            "replacements_applied": len(replacements),
            "replies": response.get("replies", []),
        }