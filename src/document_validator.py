import json
from typing import List, Dict, Any, Tuple

class DocumentValidator:
    """
    Document validator module for verifying document standardization quality:
    - Unique doc_id compliance (0 duplicates)
    - Content non-emptiness & payload validity
    - Schema structure compliance
    - JSON serialization & roundtrip integrity
    """

    def validate_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_docs = len(documents)
        doc_ids = set()
        duplicate_doc_ids = 0
        empty_content_count = 0
        schema_errors = 0
        json_serialization_errors = 0

        valid_doc_count = 0

        for doc in documents:
            is_valid = True

            # 1. Unique doc_id check
            doc_id = doc.get("doc_id")
            if not doc_id or doc_id in doc_ids:
                duplicate_doc_ids += 1
                is_valid = False
            else:
                doc_ids.add(doc_id)

            # 2. Content validity check
            content = doc.get("content")
            if not content or not isinstance(content, str) or str(content).strip() == "":
                empty_content_count += 1
                is_valid = False

            # 3. Schema structure check
            required_keys = ["doc_id", "title", "content", "metadata", "processing_info"]
            if not all(k in doc for k in required_keys):
                schema_errors += 1
                is_valid = False

            # 4. JSON roundtrip serialization check
            try:
                serialized = json.dumps(doc, ensure_ascii=False)
                deserialized = json.loads(serialized)
                if deserialized.get("doc_id") != doc.get("doc_id"):
                    json_serialization_errors += 1
                    is_valid = False
            except Exception:
                json_serialization_errors += 1
                is_valid = False

            if is_valid:
                valid_doc_count += 1

        validation_stats = {
            "total_documents_inspected": total_docs,
            "valid_documents_count": valid_doc_count,
            "validation_success_rate_pct": round((valid_doc_count / total_docs) * 100, 2) if total_docs > 0 else 0.0,
            "duplicate_doc_ids_count": duplicate_doc_ids,
            "empty_content_count": empty_content_count,
            "schema_errors_count": schema_errors,
            "json_serialization_errors_count": json_serialization_errors
        }

        return validation_stats
