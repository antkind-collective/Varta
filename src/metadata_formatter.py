import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

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
    def format_metadata(row: pd.Series) -> Dict[str, Any]:
        def clean_val(val: Any) -> Optional[Any]:
            if pd.isna(val) or val is None:
                return None
            val_str = str(val).strip()
            if val_str == "" or val_str.lower() == "nan" or val_str.lower() == "none":
                return None
            return val

        # Handle numeric user_rating
        rating_raw = clean_val(row.get("user_rating"))
        user_rating = None
        if rating_raw is not None:
            try:
                user_rating = float(rating_raw)
            except (ValueError, TypeError):
                user_rating = None

        metadata = {
            "post_id": clean_val(row.get("post_id")),
            "source_type": clean_val(row.get("source_type")),
            "category_taxonomy": clean_val(row.get("category_taxonomy")),
            "image_url": clean_val(row.get("image_url")),
            "user_rating": user_rating
        }

        return metadata
