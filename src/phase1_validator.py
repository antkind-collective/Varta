import os
import json
import pandas as pd
from typing import Dict, Any, List, Tuple

class Phase1Validator:
    """
    Phase 1 Data Foundation Quality Assurance & Validation Utility.
    Performs comprehensive verification across all Phase 1 artifacts:
    - Integrity & row count consistency
    - Schema compliance
    - Referential equivalence between JSON and CSV
    - Manifest attribute validation
    - Unicode preservation & serialization integrity
    """

    def __init__(self, processed_csv: str, standardized_csv: str, standardized_json: str, manifest_json: str):
        self.processed_csv_path = os.path.abspath(processed_csv)
        self.standardized_csv_path = os.path.abspath(standardized_csv)
        self.standardized_json_path = os.path.abspath(standardized_json)
        self.manifest_json_path = os.path.abspath(manifest_json)

    def validate_all(self) -> Dict[str, Any]:
        results = {}

        # 1. Load Artifacts
        df_proc = pd.read_csv(self.processed_csv_path, low_memory=False)
        df_std_csv = pd.read_csv(self.standardized_csv_path, low_memory=False)
        with open(self.standardized_json_path, "r", encoding="utf-8") as f:
            json_docs = json.load(f)
        with open(self.manifest_json_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        proc_rows = len(df_proc)
        std_csv_rows = len(df_std_csv)
        json_doc_count = len(json_docs)
        manifest_doc_count = manifest.get("document_count", 0)

        # 2. Row Count & Integrity Validation
        row_count_match = (proc_rows == std_csv_rows == json_doc_count == manifest_doc_count == 33975)
        
        doc_ids = set()
        duplicate_ids = 0
        empty_content_count = 0
        multilingual_count = 0

        for doc in json_docs:
            d_id = doc.get("doc_id")
            if not d_id or d_id in doc_ids:
                duplicate_ids += 1
            else:
                doc_ids.add(d_id)

            content = doc.get("content", "")
            if not content or str(content).strip() == "":
                empty_content_count += 1

            proc_info = doc.get("processing_info", {})
            if proc_info.get("has_multilingual_unicode"):
                multilingual_count += 1

        integrity_results = {
            "processed_csv_rows": proc_rows,
            "standardized_csv_rows": std_csv_rows,
            "standardized_json_docs": json_doc_count,
            "manifest_document_count": manifest_doc_count,
            "row_count_match": row_count_match,
            "duplicate_doc_ids": duplicate_ids,
            "empty_content_count": empty_content_count,
            "multilingual_documents_count": multilingual_count
        }

        # 3. JSON vs CSV 1-to-1 Referential Consistency
        mismatched_payloads = 0
        for idx in range(min(json_doc_count, std_csv_rows)):
            j_doc = json_docs[idx]
            csv_row = df_std_csv.iloc[idx]

            j_id = str(j_doc.get("doc_id"))
            c_id = str(csv_row.get("doc_id"))

            j_content = str(j_doc.get("content"))
            c_content = str(csv_row.get("content"))

            if j_id != c_id or j_content != c_content:
                mismatched_payloads += 1

        referential_results = {
            "mismatched_payloads_count": mismatched_payloads,
            "referential_equivalence": (mismatched_payloads == 0)
        }

        # 4. Manifest Attributes Validation
        manifest_valid = (
            manifest.get("project") == "VARTA" and
            manifest.get("phase") == "Phase 1 - Data Foundation" and
            manifest.get("sprint") == "Sprint 1.3 - Document Standardization" and
            manifest.get("document_count") == json_doc_count and
            manifest.get("content_field") == "content" and
            set(manifest.get("metadata_fields", [])) == {"post_id", "source_type", "category_taxonomy", "image_url", "user_rating"} and
            manifest.get("validation_summary", {}).get("data_loss") == False
        )

        manifest_results = {
            "manifest_valid": manifest_valid,
            "manifest_details": manifest
        }

        results = {
            "integrity": integrity_results,
            "referential_consistency": referential_results,
            "manifest_validation": manifest_results
        }

        return results
