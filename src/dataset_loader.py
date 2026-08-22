import os
import pandas as pd
from typing import Tuple, Dict, Any, Optional, List, Generator

class DatasetLoader:
    """
    Dataset loader for loading and extracting basic file-level metrics dynamically.
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

    def load_dataset(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Loads dataset into pandas DataFrame supporting .csv, .json, and .jsonl files.
        """
        ext = os.path.splitext(self.file_path)[1].lower()
        if ext == ".jsonl":
            df = pd.read_json(self.file_path, lines=True)
        elif ext == ".json":
            try:
                df = pd.read_json(self.file_path)
            except ValueError:
                # Fallback to lines=True if multi-line jsonl was named .json
                df = pd.read_json(self.file_path, lines=True)
        else:
            # Default to CSV
            df = pd.read_csv(self.file_path, low_memory=False)

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
        For CSVs, uses pd.read_csv(..., chunksize=batch_size, usecols=...) for true low-memory streaming.
        For JSON/JSONL, streams in batch slices preserving identical row semantics.
        """
        ext = os.path.splitext(self.file_path)[1].lower()

        if ext in [".jsonl", ".json"]:
            try:
                df_reader = pd.read_json(self.file_path, lines=(ext == ".jsonl"), chunksize=batch_size)
                if hasattr(df_reader, "__iter__"):
                    for chunk_df in df_reader:
                        yield chunk_df
                    return
            except Exception:
                pass

            # Fallback for standard JSON arrays
            try:
                df_full = pd.read_json(self.file_path)
            except ValueError:
                df_full = pd.read_json(self.file_path, lines=True)

            if isinstance(df_full, pd.DataFrame):
                for i in range(0, len(df_full), batch_size):
                    yield df_full.iloc[i : i + batch_size].copy()
        else:
            # True streaming CSV reader
            if columns_to_drop:
                head_cols = list(pd.read_csv(self.file_path, nrows=0).columns)
                drop_set = set(columns_to_drop)
                use_cols = [c for c in head_cols if c not in drop_set]
                for chunk_df in pd.read_csv(self.file_path, usecols=use_cols, chunksize=batch_size, low_memory=False):
                    yield chunk_df
            else:
                for chunk_df in pd.read_csv(self.file_path, chunksize=batch_size, low_memory=False):
                    yield chunk_df
