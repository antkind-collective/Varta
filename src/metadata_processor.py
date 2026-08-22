import pandas as pd
import numpy as np
import re
from typing import Dict, Any, Tuple

class MetadataProcessor:
    """
    Metadata processor module for standardizing validated metadata attributes:
    - source_type (casing & whitespace trimming)
    - category_taxonomy (taxonomy tag normalization)
    - image_url (URL trimming & validation)
    - user_rating (numeric float conversion)
    
    Preserves missing optional metadata as explicit nulls (NaN) without fabricating strings.
    """

    def __init__(self):
        self.url_pattern = re.compile(r'^(?:https?://|www\.)\S+$', re.IGNORECASE)

    def process_metadata(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        processed_df = df.copy()
        stats = {}

        # 1. source_type
        if "source_type" in processed_df.columns:
            raw_series = processed_df["source_type"].dropna().astype(str)
            cleaned = raw_series.str.strip().str.title()
            processed_df["source_type"] = cleaned.reindex(processed_df.index)
            stats["source_type_unique_count"] = int(processed_df["source_type"].nunique(dropna=True))
            stats["source_type_null_count"] = int(processed_df["source_type"].isna().sum())

        # 2. category_taxonomy
        if "category_taxonomy" in processed_df.columns:
            raw_series = processed_df["category_taxonomy"].dropna().astype(str)
            # Normalize '|' delimiters with single spaces
            cleaned = raw_series.apply(lambda val: " | ".join([part.strip().title() for part in val.split("|") if part.strip()]) if val.strip() else None)
            processed_df["category_taxonomy"] = cleaned.reindex(processed_df.index)
            stats["category_taxonomy_non_null_count"] = int(processed_df["category_taxonomy"].notna().sum())
            stats["category_taxonomy_null_count"] = int(processed_df["category_taxonomy"].isna().sum())

        # 3. image_url
        if "image_url" in processed_df.columns:
            raw_series = processed_df["image_url"].dropna().astype(str).str.strip()
            # Validate URL or set NaN
            valid_urls = raw_series.apply(lambda url: url if self.url_pattern.match(url) else None)
            processed_df["image_url"] = valid_urls.reindex(processed_df.index)
            stats["image_url_valid_count"] = int(processed_df["image_url"].notna().sum())
            stats["image_url_null_count"] = int(processed_df["image_url"].isna().sum())

        # 4. user_rating
        if "user_rating" in processed_df.columns:
            numeric_ratings = pd.to_numeric(processed_df["user_rating"], errors="coerce")
            processed_df["user_rating"] = numeric_ratings
            stats["user_rating_valid_count"] = int(processed_df["user_rating"].notna().sum())
            stats["user_rating_null_count"] = int(processed_df["user_rating"].isna().sum())

        # 5. source_url (Validate URL & strip scraper suffixes)
        if "source_url" in processed_df.columns:
            raw_series = processed_df["source_url"].dropna().astype(str).str.strip()
            def clean_source_url(val: str) -> Any:
                if not val or val.lower() in ["nan", "none"]:
                    return None
                val_clean = re.sub(r'\.\d+$', '', val)
                return val_clean if self.url_pattern.match(val_clean) else None
            valid_source_urls = raw_series.apply(clean_source_url)
            processed_df["source_url"] = valid_source_urls.reindex(processed_df.index)
            stats["source_url_valid_count"] = int(processed_df["source_url"].notna().sum())
            stats["source_url_null_count"] = int(processed_df["source_url"].isna().sum())

        return processed_df, stats
