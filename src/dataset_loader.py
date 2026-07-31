import os
import pandas as pd
from typing import Tuple, Dict, Any

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
        Loads dataset into pandas DataFrame and computes basic discovery metrics.
        """
        df = pd.read_csv(self.file_path, low_memory=False)
        meta = self.get_file_metadata()

        memory_usage_bytes = df.memory_usage(deep=True).sum()
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
