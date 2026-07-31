import os
import json
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Tuple

from src.dataset_loader import DatasetLoader
from src.data_cleaner import DataCleaner
from src.text_normalizer import TextNormalizer
from src.metadata_processor import MetadataProcessor
from src.duplicate_handler import DuplicateHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PreprocessingPipeline")

class PreprocessingPipeline:
    """
    Orchestrates the generic data cleaning and preprocessing pipeline:
    1. Dataset loading
    2. Column pruning & renaming
    3. Payload filtering & identifier hash generation
    4. Text normalization with Unicode preservation
    5. Metadata standardization
    6. Multi-level deduplication
    7. Exporting clean dataset to data/processed/processed_dataset.csv
    8. Writing narrative report & cleaning statistics
    """

    def __init__(self, raw_data_path: str, config_path: str, output_dir: str, reports_dir: str):
        self.raw_data_path = os.path.abspath(raw_data_path)
        self.config_path = os.path.abspath(config_path)
        self.output_dir = os.path.abspath(output_dir)
        self.reports_dir = os.path.abspath(reports_dir)

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def run_pipeline(self) -> Tuple[str, Dict[str, Any]]:
        logger.info(f"Starting Preprocessing Pipeline for dataset: {self.raw_data_path}")

        # 1. Load Raw Dataset
        loader = DatasetLoader(self.raw_data_path)
        df_raw, raw_meta = loader.load_dataset()
        initial_rows = len(df_raw)
        initial_cols = len(df_raw.columns)
        logger.info(f"Raw Dataset Loaded: {initial_rows:,} rows, {initial_cols} columns")

        # 2. Structural Column Pruning & Renaming
        cleaner = DataCleaner(self.config)
        df_clean_cols, struct_stats = cleaner.clean_structure_and_columns(df_raw)
        logger.info(f"Pruned {struct_stats['columns_dropped_count']} ghost columns; Renamed {struct_stats['columns_renamed_count']} columns")

        # 3. Payload Filtering & Identifier Hash Generation
        df_valid, filter_stats = cleaner.filter_and_fill_identifiers(df_clean_cols)
        logger.info(f"Filtered {filter_stats['invalid_rows_filtered']} invalid rows; Filled {filter_stats['missing_ids_filled']} missing IDs")

        # 4. Text Normalization
        normalizer = TextNormalizer()
        df_text_norm = df_valid.copy()
        text_norm_stats = {}
        for col in self.config.get("core_payload_columns", ["title", "text_content"]):
            if col in df_text_norm.columns:
                norm_series, modified_cnt = normalizer.normalize_series(df_text_norm[col])
                df_text_norm[col] = norm_series
                text_norm_stats[col] = {
                    "records_inspected": len(norm_series),
                    "records_modified": modified_cnt
                }
        logger.info("Text Normalization completed with full Unicode preservation")

        # 5. Metadata Processing
        meta_processor = MetadataProcessor()
        df_meta_clean, metadata_stats = meta_processor.process_metadata(df_text_norm)
        logger.info("Metadata standardization completed")

        # 6. Deduplication
        dup_handler = DuplicateHandler(
            id_column=self.config.get("identifier_column", "post_id"),
            payload_columns=self.config.get("core_payload_columns", ["title", "text_content"])
        )
        df_processed, dedup_stats = dup_handler.deduplicate(df_meta_clean)
        logger.info(f"Deduplication completed: {dedup_stats['total_duplicates_removed']:,} duplicates removed")

        # 7. Export Processed Dataset
        output_csv_path = os.path.join(self.output_dir, "processed_dataset.csv")
        df_processed.to_csv(output_csv_path, index=False, encoding="utf-8")
        logger.info(f"Processed Dataset Exported to: {output_csv_path}")

        # Final Statistics Aggregation
        final_rows = len(df_processed)
        final_cols = len(df_processed.columns)
        processed_file_bytes = os.path.getsize(output_csv_path)
        processed_file_mb = round(processed_file_bytes / (1024 * 1024), 2)

        pipeline_stats = {
            "raw_metadata": raw_meta,
            "processed_file_path": output_csv_path,
            "processed_file_size_mb": processed_file_mb,
            "initial_rows": initial_rows,
            "final_rows": final_rows,
            "rows_removed_total": initial_rows - final_rows,
            "initial_cols": initial_cols,
            "final_cols": final_cols,
            "columns_dropped": struct_stats["columns_dropped_count"],
            "columns_renamed": struct_stats["columns_renamed_count"],
            "invalid_rows_filtered": filter_stats["invalid_rows_filtered"],
            "missing_ids_filled": filter_stats["missing_ids_filled"],
            "text_normalization": text_norm_stats,
            "metadata_stats": metadata_stats,
            "deduplication": dedup_stats,
            "final_columns": list(df_processed.columns)
        }

        # 8. Generate Reports
        self._generate_cleaning_statistics_report(os.path.join(self.reports_dir, "cleaning_statistics.md"), pipeline_stats)
        self._generate_preprocessing_report(os.path.join(self.reports_dir, "preprocessing_report.md"), pipeline_stats)

        return output_csv_path, pipeline_stats

    def _generate_cleaning_statistics_report(self, filepath: str, stats: Dict[str, Any]):
        lines = [
            "# VARTA — Data Cleaning Statistics Report (Sprint 1.2)",
            "",
            "## 1. Executive Summary Table",
            "| Metric | Raw Dataset | Processed Dataset | Net Change |",
            "| :--- | :-: | :-: | :-: |",
            f"| **Total Rows / Records** | {stats['initial_rows']:,} | {stats['final_rows']:,} | -{stats['rows_removed_total']:,} rows |",
            f"| **Total Columns / Features** | {stats['initial_cols']} | {stats['final_cols']} | -{stats['columns_dropped']} ghost cols |",
            f"| **File Size (Disk)** | {stats['raw_metadata']['file_size_mb']} MB | {stats['processed_file_size_mb']} MB | Optimized |",
            "",
            "## 2. Quantitative Processing Metrics",
            "| Cleaning Phase | Quantity | Description |",
            "| :--- | :-: | :--- |",
            f"| **Ghost Columns Dropped** | {stats['columns_dropped']} | Confirmed empty trailing comma columns (`Unnamed: 5`..`24`) |",
            f"| **Columns Renamed** | {stats['columns_renamed']} | Mapped raw header names to clean `snake_case` names |",
            f"| **Invalid Payload Rows Filtered** | {stats['invalid_rows_filtered']:,} | Rows missing both `title` and `text_content` payload |",
            f"| **Missing Identifiers Hash-Filled** | {stats['missing_ids_filled']:,} | SHA256 content hashes generated for missing `post_id` entries |",
            f"| **Full Exact Duplicate Rows Removed** | {stats['deduplication']['full_duplicate_rows_removed']:,} | Identical rows across all fields |",
            f"| **Primary Key ID Duplicates Removed** | {stats['deduplication']['id_duplicates_removed']:,} | Duplicate `post_id` records (kept first) |",
            f"| **Content Hash Duplicates Removed** | {stats['deduplication']['content_duplicates_removed']:,} | Duplicate `title` + `text_content` payload hashes |",
            f"| **Total Deduplicated Records Removed** | {stats['deduplication']['total_duplicates_removed']:,} | Combined deduplication total |",
            "",
            "## 3. Text Normalization Summary",
            "| Column Name | Records Inspected | Records Modified | Modification % |",
            "| :--- | :-: | :-: | :-: |"
        ]

        for col, t_stat in stats["text_normalization"].items():
            pct = round((t_stat['records_modified'] / t_stat['records_inspected']) * 100, 2) if t_stat['records_inspected'] > 0 else 0.0
            lines.append(f"| `{col}` | {t_stat['records_inspected']:,} | {t_stat['records_modified']:,} | {pct}% |")

        lines.extend([
            "",
            "## 4. Final Processed Column Schema",
            "| Column Index | Field Name | Strategic Role in RAG Pipeline | Data Type |",
            "| :-: | :--- | :--- | :--- |"
        ])

        for idx, col in enumerate(stats["final_columns"], 1):
            if col in ["text_content", "title"]:
                role = "🎯 Core Vector Payload"
            elif col == "post_id":
                role = "🔑 Primary Document Reference (`doc_id` / `source_url`)"
            elif col in ["source_type", "category_taxonomy"]:
                role = "🏷️ Metadata Filter Attribute"
            else:
                role = "ℹ️ Optional Metadata Attribute"

            lines.append(f"| {idx} | `{col}` | {role} | `object / string` |")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _generate_preprocessing_report(self, filepath: str, stats: Dict[str, Any]):
        lines = [
            "# VARTA — Preprocessing Pipeline Execution Report (Sprint 1.2)",
            "",
            "## 1. Pipeline Execution Overview",
            f"- **Input Raw Dataset**: `{stats['raw_metadata']['file_name']}`",
            f"- **Output Processed Dataset**: `{stats['processed_file_path']}`",
            f"- **Output File Size**: `{stats['processed_file_size_mb']} MB`",
            f"- **Processed Records**: `{stats['final_rows']:,}` (Cleaned from initial {stats['initial_rows']:,})",
            f"- **Processed Features**: `{stats['final_cols']}` columns (Pruned from initial {stats['initial_cols']})",
            "",
            "## 2. Transformations Implemented",
            "",
            "### A. Column Pruning & Renaming",
            "1. **Ghost Column Removal**: Dropped all 20 un-named empty trailing comma columns (`Unnamed: 5` through `Unnamed: 24`).",
            "2. **Configuration-Driven Column Renaming**:",
            "   - `Post ID` $\\rightarrow$ `post_id`",
            "   - `Sound Bite Text` $\\rightarrow$ `text_content`",
            "   - `Title` $\\rightarrow$ `title`",
            "   - `Source Type` $\\rightarrow$ `source_type`",
            "   - `Unnamed: 4` $\\rightarrow$ `image_url`",
            "   - `Unnamed: 25` $\\rightarrow$ `user_rating`",
            "   - `Unnamed: 26` $\\rightarrow$ `category_taxonomy`",
            "",
            "### B. Payload Filtering & Identifier Resolution",
            "1. **Invalid Row Removal**: Filtered out rows lacking valid textual payload in both `title` and `text_content`.",
            "2. **Deterministic Hash Generation**: Filled missing `post_id` values with SHA256 hashes of `title` + `text_content` payload.",
            "",
            "### C. Text Normalization & Unicode Preservation",
            "1. **Whitespace & Line Break Normalization**: Standardized consecutive line breaks (`\\r\\n` $\\rightarrow$ `\\n`), collapsed multiple spaces, and stripped unprintable control characters.",
            "2. **Multilingual Script Integrity**: Preserved Hindi (Devanagari `\\u0900-\\u097F`), Bengali (`\\u0980-\\u09FF`), English, digits, and punctuation completely intact.",
            "",
            "### D. Multi-Level Deduplication",
            "1. **Full Row Deduplication**: Identified and removed exact duplicate records across all columns.",
            "2. **Identifier & Content Hash Deduplication**: Resolved primary key collisions (`post_id`) and content hash collisions (`title` + `text_content`).",
            "",
            "## 3. Readiness for Sprint 1.3 (Document Standardization)",
            "The output dataset `data/processed/processed_dataset.csv` is fully cleaned, standardized, and ready for document JSON serialization and chunking in Sprint 1.3."
        ]

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
