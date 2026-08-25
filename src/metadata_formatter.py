import re
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Union

class MetadataFormatter:
    """
    Metadata formatter module for organizing document metadata attributes:
    - post_id (Document identifier reference)
    - source_type (Media source type, e.g. News)
    - category_taxonomy (Category taxonomy tags, e.g. Technology | Social Media)
    - image_url (Article preview media link)
    - user_rating (Numeric user rating score)

    Ensures optional metadata fields remain explicit None/null when missing.
    """

    @staticmethod
    def format_metadata(row: Union[pd.Series, Dict[str, Any]]) -> Dict[str, Any]:
        def clean_val(val: Any) -> Optional[Any]:
            if pd.isna(val) or val is None:
                return None
            val_str = str(val).strip()
            if val_str == "" or val_str.lower() == "nan" or val_str.lower() == "none":
                return None
            if val_str.startswith("http://") or val_str.startswith("https://"):
                return re.sub(r'\.\d+$', '', val_str)
            return val_str

        # Handle numeric user_rating
        rating_raw = row.get("user_rating")
        user_rating = None
        if pd.notna(rating_raw) and rating_raw is not None:
            try:
                user_rating = float(rating_raw)
            except (ValueError, TypeError):
                user_rating = None

        post_id_val = clean_val(row.get("post_id"))
        raw_source_url = clean_val(row.get("source_url"))

        # Determine canonical source_url (only valid http/https URLs, never invented)
        source_url = None
        if raw_source_url and (raw_source_url.startswith("http://") or raw_source_url.startswith("https://")):
            source_url = raw_source_url
        elif post_id_val and (post_id_val.startswith("http://") or post_id_val.startswith("https://")):
            source_url = post_id_val

        metadata = {
            "post_id": post_id_val,
            "source_url": source_url,
            "source_type": clean_val(row.get("source_type")),
            "category_taxonomy": clean_val(row.get("category_taxonomy")),
            "image_url": clean_val(row.get("image_url")),
            "user_rating": user_rating,
            "context_relevance_score": float(row.get("context_relevance_score")) if pd.notna(row.get("context_relevance_score")) else 1.0,
            "data_quality_score": float(row.get("data_quality_score")) if pd.notna(row.get("data_quality_score")) else 1.0,
            "relevance_decision": str(row.get("relevance_decision")) if pd.notna(row.get("relevance_decision")) else "KEEP",
            "relevance_reason": str(row.get("relevance_reason")) if pd.notna(row.get("relevance_reason")) else "DEFAULT_KEEP"
        }

        return metadata
