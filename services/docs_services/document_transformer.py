import json

class DocumentTransformer:
    """Transforms a raw Google Doc JSON into a simplified payload for the LLM."""

    @staticmethod
    def transform_to_payload(document_tab: dict) -> str:
        """Returns a JSON string of the structured document contents."""
        elements = DocumentTransformer._parse_content(
            document_tab.get("body", {}).get("content", []),
            document_tab.get("inlineObjects", {})
        )
        return json.dumps(elements, indent=2)

    @staticmethod
    def _parse_content(content: list, inline_objects: dict) -> list[dict]:
        elements = []
        for item in content:
            if "paragraph" in item:
                para_text = ""
                images_in_para = []
                for el in item["paragraph"].get("elements", []):
                    # Text elements
                    if "textRun" in el:
                        para_text += el.get("textRun", {}).get("content", "")
                    # Image elements
                    elif "inlineObjectElement" in el:
                        obj_id = el["inlineObjectElement"].get("inlineObjectId")
                        if obj_id and obj_id in inline_objects:
                            uri = (
                                inline_objects[obj_id]
                                .get("inlineObjectProperties", {})
                                .get("embeddedObject", {})
                                .get("imageProperties", {})
                                .get("contentUri")
                            )
                            if uri:
                                images_in_para.append(uri)
                
                para_text = para_text.strip()
                if para_text:
                    elements.append({"type": "text", "content": para_text})
                
                for uri in images_in_para:
                    elements.append({"type": "image", "url": uri})
                    
            elif "table" in item:
                table_data = []
                for row in item["table"].get("tableRows", []):
                    row_data = []
                    for cell in row.get("tableCells", []):
                        cell_text = DocumentTransformer._extract_text_only(cell.get("content", []))
                        row_data.append(cell_text.strip())
                    table_data.append(row_data)
                
                if table_data:
                    elements.append({"type": "table", "rows": table_data})

        return elements

    @staticmethod
    def _extract_text_only(content: list) -> str:
        """Helper to extract flat text from nested structures like table cells."""
        text = ""
        for item in content:
            if "paragraph" in item:
                for el in item["paragraph"].get("elements", []):
                    if "textRun" in el:
                        text += el.get("textRun", {}).get("content", "")
            elif "table" in item:
                for row in item["table"].get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        text += DocumentTransformer._extract_text_only(cell.get("content", [])) + " "
        return text
