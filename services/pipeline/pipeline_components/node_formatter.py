"""TransformComponent that restructures node metadata before embedding."""

from typing import Sequence

from llama_index.core.schema import BaseNode, TransformComponent


class NodeTextFormatter(TransformComponent):
    """Restructure node metadata and set node.text to the subject for embedding.

    After this component runs, each node will have:
    - ``node.text`` = subject (used by downstream OllamaEmbedding for vector search)
    - ``node.metadata`` containing ONLY: ref_no, date, subject, full_letter,
      tab_title, source_doc_id
    """

    def __call__(self, nodes: Sequence[BaseNode], **kwargs) -> Sequence[BaseNode]:
        for node in nodes:
            ref_no = node.metadata.get("ref_no") or ""
            date = node.metadata.get("date") or ""
            subject = node.metadata.get("subject") or ""
            full_letter = node.metadata.get("full_markdown") or node.text
            tab_title = node.metadata.get("tab_title") or ""
            source_doc_id = node.metadata.get("source_doc_id") or ""

            # Rebuild metadata with only the allowed keys
            node.metadata = {
                "ref_no": ref_no,
                "date": date,
                "subject": subject,
                "full_letter": full_letter,
                "tab_title": tab_title,
                "source_doc_id": source_doc_id,
            }

            # Set node.text to subject — this is what gets embedded for vector search
            node.text = subject

        return nodes

    async def acall(self, nodes: Sequence[BaseNode], **kwargs) -> Sequence[BaseNode]:
        return self.__call__(nodes, **kwargs)
