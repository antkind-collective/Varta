import re
import pandas as pd
from typing import Dict, Any, Optional
from src.metadata_formatter import MetadataFormatter

class DocumentBuilder:
    """
    Document builder module for creating generic, standardized document objects:
    - doc_id: Unique document identifier
    - title: Document title / headline
    - content: Main textual content payload
    - metadata: Structured metadata attributes
    - processing_info: Content stats (word count, char count, multilingual flag) and schema version
    """

    def __init__(self, schema_version: str = "1.0.0"):
        self.schema_version = schema_version
        self.metadata_formatter = MetadataFormatter()

    def build_document(self, row: pd.Series, doc_index: int) -> Dict[str, Any]:
        raw_post_id = row.get("post_id") if pd.notna(row.get("post_id")) else (row.get("id") or row.get("doc_id") or row.get("source_url"))
        post_id_clean = str(raw_post_id).strip() if pd.notna(raw_post_id) else ""
        
        # Generate doc_id: use post_id if valid string, else pad index
        if post_id_clean and post_id_clean.lower() != "nan" and post_id_clean.lower() != "none":
            if post_id_clean.startswith("http://") or post_id_clean.startswith("https://"):
                # Strip accidental scraper suffix (e.g. .1) to preserve canonical URL
                doc_id = re.sub(r'\.\d+$', '', post_id_clean)
            else:
                doc_id = post_id_clean
        else:
            doc_id = f"doc_{doc_index:06d}"

        # Extract title & content
        raw_title = row.get("title")
        title = str(raw_title).strip() if pd.notna(raw_title) and str(raw_title).strip().lower() not in ["", "nan", "none"] else None
        
        raw_content = row.get("text_content")
        content = str(raw_content).strip() if pd.notna(raw_content) and str(raw_content).strip().lower() not in ["", "nan", "none"] else ""

        # Format metadata
        metadata = self.metadata_formatter.format_metadata(row)

        # Compute processing info
        char_count = len(content)
        word_count = len(content.split()) if content else 0
        has_multilingual_unicode = any(ord(c) > 127 for c in content) or (any(ord(c) > 127 for c in title) if title else False)

        processing_info = {
            "char_count": char_count,
            "word_count": word_count,
            "has_multilingual_unicode": has_multilingual_unicode,
            "schema_version": self.schema_version
        }

        return {
            "doc_id": doc_id,
            "title": title,
            "content": content,
            "metadata": metadata,
            "processing_info": processing_info
        }
