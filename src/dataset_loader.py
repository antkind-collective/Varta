import os
import pandas as pd
from typing import Tuple, Dict, Any, Optional, List, Generator

class DatasetLoader:
    """
    Dataset loader for loading and extracting basic file-level metrics dynamically.
    Supports robust multi-encoding detection and streaming chunking across .csv, .json, and .jsonl.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dataset file not found at: {file_path}")

    def get_file_metadata(self) -> Dict[str, Any]:
        file_size_bytes = os.path.getsize(self.file_path)
        file_size_mb = file_size_bytes / (1024 * 1024)
        return {
            "file_name": os.path.basename(self.file_path),
            "file_path": os.path.abspath(self.file_path),
            "file_size_bytes": file_size_bytes,
            "file_size_mb": round(file_size_mb, 2)
        }

    @staticmethod
    def _detect_csv_encoding(file_path: str) -> Tuple[str, bool]:
        """
        Tests common candidate encodings to detect the best matching charset without decoding errors.
        """
        encodings = ["utf-8", "utf-8-sig", "cp1252", "latin1", "iso-8859-1"]
        for enc in encodings:
            try:
                pd.read_csv(file_path, encoding=enc, nrows=100)
                return enc, False
            except (UnicodeDecodeError, UnicodeError):
                continue
        # Fallback to UTF-8 with character replacement if all strict encodings fail
        return "utf-8", True

    @classmethod
    def read_csv_robust(cls, file_path: str, **kwargs) -> pd.DataFrame:
        """
        Reads CSV file with automatic multi-encoding fallback and replacement.
        """
        chosen_enc, use_replace = cls._detect_csv_encoding(file_path)
        read_kwargs = dict(kwargs)
        read_kwargs["encoding"] = chosen_enc
        if use_replace:
            read_kwargs["encoding_errors"] = "replace"
        
        try:
            return pd.read_csv(file_path, **read_kwargs)
        except (UnicodeDecodeError, UnicodeError):
            read_kwargs["encoding"] = "utf-8"
            read_kwargs["encoding_errors"] = "replace"
            return pd.read_csv(file_path, **read_kwargs)

    def load_dataset(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Loads dataset into pandas DataFrame supporting .csv, .json, and .jsonl files.
        """
        ext = os.path.splitext(self.file_path)[1].lower()
        if ext == ".jsonl":
            df = pd.read_json(self.file_path, lines=True, encoding="utf-8", encoding_errors="replace")
        elif ext == ".json":
            try:
                df = pd.read_json(self.file_path, encoding="utf-8", encoding_errors="replace")
            except ValueError:
                # Fallback to lines=True if multi-line jsonl was named .json
                df = pd.read_json(self.file_path, lines=True, encoding="utf-8", encoding_errors="replace")
        else:
            # Default to CSV with encoding fallback
            df = self.read_csv_robust(self.file_path, low_memory=False)

        meta = self.get_file_metadata()

        memory_usage_bytes = df.memory_usage(deep=True).sum() if not df.empty else 0
        memory_usage_mb = memory_usage_bytes / (1024 * 1024)

        metrics = {
            **meta,
            "row_count": len(df),
            "column_count": len(df.columns),
            "memory_usage_bytes": memory_usage_bytes,
            "memory_usage_mb": round(memory_usage_mb, 2),
            "column_names": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()}
        }

        return df, metrics

    def stream_dataset_chunks(self, batch_size: int = 2000, columns_to_drop: Optional[List[str]] = None) -> Generator[pd.DataFrame, None, None]:
        """
        Streams dataset in DataFrame chunks of specified batch_size.
        For CSVs, uses pd.read_csv(..., chunksize=batch_size, usecols=...) with robust encoding fallback.
        For JSON/JSONL, streams in batch slices preserving identical row semantics.
        """
        ext = os.path.splitext(self.file_path)[1].lower()

        if ext in [".jsonl", ".json"]:
            try:
                df_reader = pd.read_json(
                    self.file_path,
                    lines=(ext == ".jsonl"),
                    chunksize=batch_size,
                    encoding="utf-8",
                    encoding_errors="replace"
                )
                if hasattr(df_reader, "__iter__"):
                    for chunk_df in df_reader:
                        yield chunk_df
                    return
            except Exception:
                pass

            # Fallback for standard JSON arrays
            try:
                df_full = pd.read_json(self.file_path, encoding="utf-8", encoding_errors="replace")
            except ValueError:
                df_full = pd.read_json(self.file_path, lines=True, encoding="utf-8", encoding_errors="replace")

            if isinstance(df_full, pd.DataFrame):
                for i in range(0, len(df_full), batch_size):
                    yield df_full.iloc[i : i + batch_size].copy()
        else:
            # True streaming CSV reader with automatic multi-encoding fallback
            chosen_enc, use_replace = self._detect_csv_encoding(self.file_path)
            read_kwargs = {
                "encoding": chosen_enc,
                "low_memory": False,
                "chunksize": batch_size
            }
            if use_replace:
                read_kwargs["encoding_errors"] = "replace"

            if columns_to_drop:
                try:
                    head_df = pd.read_csv(
                        self.file_path,
                        encoding=chosen_enc,
                        nrows=0,
                        encoding_errors="replace" if use_replace else None
                    )
                    head_cols = list(head_df.columns)
                    drop_set = set(columns_to_drop)
                    use_cols = [c for c in head_cols if c not in drop_set]
                    read_kwargs["usecols"] = use_cols
                except Exception:
                    pass

            try:
                for chunk_df in pd.read_csv(self.file_path, **read_kwargs):
                    yield chunk_df
            except (UnicodeDecodeError, UnicodeError):
                # Fallback to UTF-8 replace if a mid-file byte triggered an error
                read_kwargs["encoding"] = "utf-8"
                read_kwargs["encoding_errors"] = "replace"
                for chunk_df in pd.read_csv(self.file_path, **read_kwargs):
                    yield chunk_df
