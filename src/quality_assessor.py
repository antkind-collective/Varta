import pandas as pd
import numpy as np
from typing import Dict, Any, List

class QualityAssessor:
    """
    Performs data quality assessment on pandas DataFrame without modifying data.
    """

    def __init__(self, classifications: List[Dict[str, Any]]):
        self.classifications = {c["column"]: c for c in classifications}

    def assess_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        total_rows = len(df)
        total_cols = len(df.columns)

        # Duplicate row check (complete duplicate rows)
        duplicate_rows_count = int(df.duplicated().sum())
        duplicate_rows_pct = round((duplicate_rows_count / total_rows) * 100, 2) if total_rows > 0 else 0.0

        # Identifier duplicate check
        id_cols = [c["column"] for c in self.classifications.values() if c["category"] == "Identifier"]
        id_duplicates = {}
        for id_col in id_cols:
            if id_col in df.columns:
                non_null_ids = df[id_col].dropna()
                dups = int(non_null_ids.duplicated().sum())
                id_duplicates[id_col] = {
                    "duplicate_count": dups,
                    "duplicate_pct": round((dups / len(non_null_ids)) * 100, 2) if len(non_null_ids) > 0 else 0.0
                }

        # Column-by-column quality metrics
        column_metrics = []
        unnamed_empty_cols = []

        for col in df.columns:
            series = df[col]
            null_count = int(series.isna().sum())
            null_pct = round((null_count / total_rows) * 100, 2) if total_rows > 0 else 0.0

            # Empty string check (for object/string dtypes)
            empty_string_count = 0
            if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
                str_series = series.dropna().astype(str)
                empty_string_count = int((str_series.str.strip() == "").sum())

            total_missing_or_empty = null_count + empty_string_count
            total_missing_pct = round((total_missing_or_empty / total_rows) * 100, 2) if total_rows > 0 else 0.0

            unique_count = int(series.nunique(dropna=True))

            col_str = str(col).strip()
            is_unnamed = col_str.startswith("Unnamed:") or col_str == ""

            if is_unnamed and total_missing_pct == 100.0:
                unnamed_empty_cols.append(col)

            column_metrics.append({
                "column": col,
                "data_type": str(series.dtype),
                "null_count": null_count,
                "null_pct": null_pct,
                "empty_string_count": empty_string_count,
                "total_missing_count": total_missing_or_empty,
                "total_missing_pct": total_missing_pct,
                "unique_count": unique_count,
                "is_unnamed": is_unnamed,
                "category": self.classifications.get(col, {}).get("category", "Unknown")
            })

        return {
            "total_rows": total_rows,
            "total_cols": total_cols,
            "duplicate_rows_count": duplicate_rows_count,
            "duplicate_rows_pct": duplicate_rows_pct,
            "id_duplicates": id_duplicates,
            "column_metrics": column_metrics,
            "unnamed_empty_cols_count": len(unnamed_empty_cols),
            "unnamed_empty_cols": unnamed_empty_cols
        }
