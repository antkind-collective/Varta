import hashlib
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple

class DataCleaner:
    """
    Data cleaner module for dataset-agnostic structural cleaning:
    - Pruning ghost columns based on configuration
    - Renaming columns to standardized snake_case based on configuration
    - Filtering invalid records missing both title and text content
    - Generating deterministic fallback post_id hashes for missing identifiers
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.column_rename_map = config.get("column_rename_map", {})
        self.columns_to_drop = config.get("columns_to_drop", [])
        self.core_payload_columns = config.get("core_payload_columns", ["title", "text_content"])
        self.id_column = config.get("identifier_column", "post_id")

    def clean_structure_and_columns(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        initial_cols = list(df.columns)
        initial_col_count = len(initial_cols)
        stats = {
            "initial_column_count": initial_col_count,
            "columns_dropped": [],
            "columns_renamed": {}
        }

        # 1. Prune ghost columns
        existing_cols_to_drop = [c for c in self.columns_to_drop if c in df.columns]
        df_pruned = df.drop(columns=existing_cols_to_drop)
        stats["columns_dropped"] = existing_cols_to_drop
        stats["columns_dropped_count"] = len(existing_cols_to_drop)

        # 2. Rename columns
        existing_rename_map = {k: v for k, v in self.column_rename_map.items() if k in df_pruned.columns}
        df_renamed = df_pruned.rename(columns=existing_rename_map)
        stats["columns_renamed"] = existing_rename_map
        stats["columns_renamed_count"] = len(existing_rename_map)
        stats["final_column_count"] = len(df_renamed.columns)
        stats["final_columns"] = list(df_renamed.columns)

        return df_renamed, stats

    def filter_and_fill_identifiers(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        initial_row_count = len(df)
        stats = {}

        # 1. Filter out records where both title AND text_content are null/empty
        payload_cols = [c for c in self.core_payload_columns if c in df.columns]
        if payload_cols:
            is_empty_mask = pd.Series(True, index=df.index)
            for c in payload_cols:
                col_str = df[c].astype(str).str.strip()
                col_valid = (df[c].notna()) & (col_str != "") & (col_str != "nan")
                is_empty_mask = is_empty_mask & (~col_valid)

            filtered_df = df[~is_empty_mask].copy()
            rows_filtered_out = initial_row_count - len(filtered_df)
        else:
            filtered_df = df.copy()
            rows_filtered_out = 0

        stats["initial_row_count"] = initial_row_count
        stats["invalid_rows_filtered"] = rows_filtered_out
        stats["rows_remaining"] = len(filtered_df)

        # 2. Handle missing post_id by generating SHA256 content hashes
        missing_ids_filled = 0
        if self.id_column in filtered_df.columns:
            id_series = filtered_df[self.id_column]
            missing_mask = id_series.isna() | (id_series.astype(str).str.strip() == "") | (id_series.astype(str).str.strip() == "nan")
            missing_ids_filled = int(missing_mask.sum())

            if missing_ids_filled > 0:
                payload_str = filtered_df.loc[missing_mask, payload_cols].fillna("").astype(str).agg(" ".join, axis=1)
                generated_hashes = payload_str.apply(
                    lambda text: f"hash_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"
                )
                filtered_df.loc[missing_mask, self.id_column] = generated_hashes

        stats["missing_ids_filled"] = missing_ids_filled
        return filtered_df, stats
