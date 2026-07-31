import pandas as pd
import numpy as np
import re
from typing import Dict, Any, List

class SchemaClassifier:
    """
    Dynamically classifies dataset columns into semantic categories:
    - Identifier
    - Text
    - Metadata
    - Categorical
    - Numeric
    - Date/Time
    - Other
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cat_threshold = config.get("categorical_ratio_threshold", 0.05)
        self.id_threshold = config.get("identifier_uniqueness_threshold", 0.85)
        self.text_avg_len_threshold = config.get("text_avg_len_threshold", 40)

    def classify_columns(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        classifications = []
        total_rows = len(df)

        for col in df.columns:
            series = df[col]
            non_null_series = series.dropna()
            non_null_count = len(non_null_series)
            unique_count = non_null_series.nunique()
            uniqueness_ratio = (unique_count / total_rows) if total_rows > 0 else 0
            col_str = str(col).strip()

            # Check 1: Empty / Unnamed ghost column ("Other")
            if non_null_count == 0:
                classifications.append({
                    "column": col,
                    "category": "Other",
                    "reasoning": "Column contains 100% missing / null values across all rows.",
                    "unique_count": 0,
                    "uniqueness_ratio": 0.0,
                    "data_type": str(series.dtype)
                })
                continue

            if col_str.startswith("Unnamed:") or col_str == "":
                # Check if it's completely empty or almost empty whitespace
                non_empty_vals = non_null_series.astype(str).str.strip()
                non_empty_vals = non_empty_vals[non_empty_vals != ""]
                if len(non_empty_vals) == 0:
                    classifications.append({
                        "column": col,
                        "category": "Other",
                        "reasoning": f"Unnamed trailing ghost column ('{col}') with 0 valid non-empty entries.",
                        "unique_count": 0,
                        "uniqueness_ratio": 0.0,
                        "data_type": str(series.dtype)
                    })
                    continue

            # Convert non-null to string for text/pattern checking
            sample_str = non_null_series.astype(str)
            avg_char_len = sample_str.str.len().mean() if len(sample_str) > 0 else 0
            max_char_len = sample_str.str.len().max() if len(sample_str) > 0 else 0

            # Check 2: Numeric
            if pd.api.types.is_numeric_dtype(series):
                if uniqueness_ratio < self.cat_threshold and unique_count <= 20:
                    category = "Categorical"
                    reasoning = f"Numeric data type with low unique value count ({unique_count} unique values), acting as a categorical code/status."
                else:
                    category = "Numeric"
                    reasoning = f"Numeric data type ({series.dtype}) with range [{non_null_series.min()}, {non_null_series.max()}]."
                
                classifications.append({
                    "column": col,
                    "category": category,
                    "reasoning": reasoning,
                    "unique_count": unique_count,
                    "uniqueness_ratio": round(uniqueness_ratio, 4),
                    "data_type": str(series.dtype)
                })
                continue

            # Check 3: Date/Time
            is_datetime = pd.api.types.is_datetime64_any_dtype(series)
            if not is_datetime and non_null_count > 0 and ("date" in col_str.lower() or "time" in col_str.lower() or "timestamp" in col_str.lower()):
                try:
                    pd.to_datetime(non_null_series.head(100), errors="raise")
                    is_datetime = True
                except Exception:
                    is_datetime = False

            if is_datetime:
                classifications.append({
                    "column": col,
                    "category": "Date/Time",
                    "reasoning": "Parseable temporal timestamps or date format.",
                    "unique_count": unique_count,
                    "uniqueness_ratio": round(uniqueness_ratio, 4),
                    "data_type": str(series.dtype)
                })
                continue

            # Check 4: Identifier
            col_name_indicates_id = any(k in col_str.lower() for k in ["id", "url", "uri", "link", "uuid", "guid", "code", "key", "post id"])
            sample_has_urls = sample_str.head(50).str.contains(r"^https?://", regex=True).mean() > 0.5
            
            if (uniqueness_ratio >= self.id_threshold or col_name_indicates_id or sample_has_urls) and avg_char_len < 300 and unique_count > 100:
                classifications.append({
                    "column": col,
                    "category": "Identifier",
                    "reasoning": f"High cardinality (uniqueness ratio: {uniqueness_ratio:.2%}) with ID/URL patterns or explicit primary key naming ('{col}').",
                    "unique_count": unique_count,
                    "uniqueness_ratio": round(uniqueness_ratio, 4),
                    "data_type": str(series.dtype)
                })
                continue

            # Check 5: Text (Free-form content)
            if avg_char_len >= self.text_avg_len_threshold or max_char_len > 200 or "text" in col_str.lower() or "title" in col_str.lower() or "content" in col_str.lower() or "body" in col_str.lower():
                classifications.append({
                    "column": col,
                    "category": "Text",
                    "reasoning": f"Free-form textual content with average length of {avg_char_len:.1f} characters (max: {max_char_len}). Suitable for semantic embedding and chunking.",
                    "unique_count": unique_count,
                    "uniqueness_ratio": round(uniqueness_ratio, 4),
                    "data_type": str(series.dtype)
                })
                continue

            # Check 6: Categorical / Metadata
            if uniqueness_ratio < self.cat_threshold or unique_count <= 100:
                col_is_meta = any(k in col_str.lower() for k in ["source", "type", "category", "author", "publisher", "region", "state", "lang", "status"])
                category = "Metadata" if col_is_meta else "Categorical"
                reasoning = f"Low cardinality discrete set ({unique_count} unique values across {total_rows} rows). Functions as {'domain metadata' if col_is_meta else 'categorical field'}."

                classifications.append({
                    "column": col,
                    "category": category,
                    "reasoning": reasoning,
                    "unique_count": unique_count,
                    "uniqueness_ratio": round(uniqueness_ratio, 4),
                    "data_type": str(series.dtype)
                })
                continue

            # Fallback: Metadata / Text
            classifications.append({
                "column": col,
                "category": "Metadata",
                "reasoning": f"General categorical/string attribute with {unique_count} unique entries.",
                "unique_count": unique_count,
                "uniqueness_ratio": round(uniqueness_ratio, 4),
                "data_type": str(series.dtype)
            })

        return classifications
