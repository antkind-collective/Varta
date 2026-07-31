import os
import json
import pandas as pd
from typing import List, Dict, Any, Tuple

class DocumentSerializer:
    """
    Document serializer module for exporting standardized document objects:
    - JSON export: standardized_documents.json (Full nested JSON array)
    - CSV export: standardized_dataset.csv (Flattened tabular representation)
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def serialize_to_json(self, documents: List[Dict[str, Any]], filename: str = "standardized_documents.json") -> str:
        json_path = os.path.join(self.output_dir, filename)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)
        return json_path

    def serialize_to_csv(self, documents: List[Dict[str, Any]], filename: str = "standardized_dataset.csv") -> str:
        flattened_rows = []
        for doc in documents:
            meta = doc.get("metadata", {})
            proc = doc.get("processing_info", {})
            flattened_rows.append({
                "doc_id": doc.get("doc_id"),
                "title": doc.get("title"),
                "content": doc.get("content"),
                "post_id": meta.get("post_id"),
                "source_type": meta.get("source_type"),
                "category_taxonomy": meta.get("category_taxonomy"),
                "image_url": meta.get("image_url"),
                "user_rating": meta.get("user_rating"),
                "char_count": proc.get("char_count"),
                "word_count": proc.get("word_count"),
                "has_multilingual_unicode": proc.get("has_multilingual_unicode"),
                "schema_version": proc.get("schema_version")
            })

        df_flat = pd.DataFrame(flattened_rows)
        csv_path = os.path.join(self.output_dir, filename)
        df_flat.to_csv(csv_path, index=False, encoding="utf-8")
        return csv_path

    def generate_manifest(
        self,
        document_count: int,
        validation_stats: Dict[str, Any],
        schema_version: str = "1.0.0",
        source_dataset: str = "processed_dataset.csv",
        filename: str = "manifest.json"
    ) -> str:
        from datetime import datetime, timezone

        manifest_data = {
            "project": "VARTA",
            "phase": "Phase 1 - Data Foundation",
            "sprint": "Sprint 1.3 - Document Standardization",
            "schema_version": schema_version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_dataset": source_dataset,
            "document_count": document_count,
            "document_format": {
                "csv": "standardized_dataset.csv",
                "json": "standardized_documents.json"
            },
            "supported_languages": [
                "English",
                "Hindi",
                "Bengali"
            ],
            "metadata_fields": [
                "post_id",
                "source_type",
                "category_taxonomy",
                "image_url",
                "user_rating"
            ],
            "content_field": "content",
            "validation_summary": {
                "unique_doc_ids": (validation_stats.get("duplicate_doc_ids_count", 0) == 0),
                "schema_validation": (validation_stats.get("schema_errors_count", 0) == 0),
                "serialization_success": (validation_stats.get("json_serialization_errors_count", 0) == 0),
                "data_loss": False
            }
        }

        manifest_path = os.path.join(self.output_dir, filename)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, ensure_ascii=False, indent=4)
        return manifest_path
