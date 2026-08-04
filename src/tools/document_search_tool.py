from typing import Dict, Any, Optional
from src.tools.base_tool import BaseTool
from src.vector_database import VectorDatabase

class DocumentSearchTool(BaseTool):
    """
    Document Search Tool for querying document metadata, titles, and source types.
    """

    def __init__(self, vector_db: Optional[VectorDatabase] = None):
        self.vector_db = vector_db

    @property
    def tool_name(self) -> str:
        return "document_search"

    @property
    def tool_description(self) -> str:
        return "Searches indexed document metadata, titles, document IDs, and source provenance."

    def validate(self, input_data: Dict[str, Any]) -> bool:
        if not isinstance(input_data, dict):
            return False
        query = input_data.get("query") or input_data.get("keyword")
        return bool(query and isinstance(query, str) and query.strip())

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate(input_data):
            return {
                "success": False,
                "error": "Invalid search term for DocumentSearchTool.",
                "matched_documents": []
            }

        search_term = (input_data.get("query") or input_data.get("keyword")).strip().lower()
        matched_docs = []

        if self.vector_db and hasattr(self.vector_db, "entries"):
            seen_ids = set()
            for entry in self.vector_db.entries.values():
                title = (entry.metadata.get("title") or "").lower() if entry.metadata else ""
                doc_id = entry.doc_id.lower()
                text_snippet = (entry.text or "").lower()

                if search_term in title or search_term in doc_id or search_term in text_snippet:
                    if entry.doc_id not in seen_ids:
                        seen_ids.add(entry.doc_id)
                        matched_docs.append({
                            "doc_id": entry.doc_id,
                            "title": entry.metadata.get("title", "Untitled") if entry.metadata else "Untitled",
                            "chunk_count": 1,
                            "snippet": entry.text[:150] + "..." if len(entry.text) > 150 else entry.text
                        })

        summary = f"Found {len(matched_docs)} matching documents for '{search_term}'."
        return {
            "success": True,
            "tool_name": self.tool_name,
            "answer": summary,
            "matched_documents": matched_docs,
            "count": len(matched_docs)
        }
