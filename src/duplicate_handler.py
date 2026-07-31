import hashlib
import pandas as pd
from typing import Dict, Any, Tuple

class DuplicateHandler:
    """
    Duplicate handler module for detecting and removing:
    - Full row exact duplicates
    - Primary key (post_id) duplicates
    - Exact payload content duplicates (title + text_content hash collision)
    """

    def __init__(self, id_column: str = "post_id", payload_columns: list = None):
        self.id_column = id_column
        self.payload_columns = payload_columns or ["title", "text_content"]

    def deduplicate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        initial_count = len(df)
        
        # Step 1: Full row duplicate removal
        df_no_full_dups = df.drop_duplicates(keep="first")
        full_dups_removed = initial_count - len(df_no_full_dups)

        # Step 2: Primary key (post_id) deduplication if column exists
        id_dups_removed = 0
        if self.id_column in df_no_full_dups.columns:
            # Only count non-null ID duplicates
            valid_ids = df_no_full_dups[df_no_full_dups[self.id_column].notna()]
            df_no_id_dups = df_no_full_dups.drop_duplicates(subset=[self.id_column], keep="first")
            id_dups_removed = len(df_no_full_dups) - len(df_no_id_dups)
            df_working = df_no_id_dups
        else:
            df_working = df_no_full_dups

        # Step 3: Content hash deduplication (title + text_content)
        content_dups_removed = 0
        avail_payload_cols = [c for c in self.payload_columns if c in df_working.columns]
        if avail_payload_cols:
            content_series = df_working[avail_payload_cols].fillna("").astype(str).agg(" ".join, axis=1)
            content_hashes = content_series.apply(lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest() if text.strip() else None)
            
            # Keep first occurrence of content hash
            df_working_temp = df_working.copy()
            df_working_temp["_content_hash"] = content_hashes
            
            # Drop where content hash is duplicated (excluding null content)
            valid_hash_df = df_working_temp[df_working_temp["_content_hash"].notna()]
            null_hash_df = df_working_temp[df_working_temp["_content_hash"].isna()]
            
            deduped_hash_df = valid_hash_df.drop_duplicates(subset=["_content_hash"], keep="first")
            content_dups_removed = len(valid_hash_df) - len(deduped_hash_df)
            
            final_df = pd.concat([deduped_hash_df, null_hash_df]).drop(columns=["_content_hash"]).sort_index()
        else:
            final_df = df_working

        final_count = len(final_df)
        total_dups_removed = initial_count - final_count

        stats = {
            "initial_record_count": initial_count,
            "full_duplicate_rows_removed": full_dups_removed,
            "id_duplicates_removed": id_dups_removed,
            "content_duplicates_removed": content_dups_removed,
            "total_duplicates_removed": total_dups_removed,
            "final_record_count": final_count
        }

        return final_df, stats
