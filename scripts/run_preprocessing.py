#!/usr/bin/env python3
"""
VARTA Phase 1 - Sprint 1.2: Data Preprocessing Pipeline CLI Script.

Executes the generic data cleaning, text normalization, metadata processing,
and deduplication pipeline, exporting the cleaned dataset to data/processed/.
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.preprocessing_pipeline import PreprocessingPipeline

def find_default_dataset(data_dir: str) -> str:
    """Locates the raw CSV dataset inside data_dir (skipping data/processed)."""
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Data directory '{data_dir}' does not exist.")
    
    for item in os.listdir(data_dir):
        full_path = os.path.join(data_dir, item)
        if os.path.isfile(full_path) and item.endswith(".csv"):
            return full_path

    raise FileNotFoundError(f"No CSV dataset found inside '{data_dir}'.")

def main():
    parser = argparse.ArgumentParser(description="VARTA Data Preprocessing Pipeline")
    parser.add_argument("--data-path", type=str, help="Path to input raw CSV dataset. Default: auto-discovers in data/")
    parser.add_argument("--config-path", type=str, default=str(project_root / "config" / "column_mapping.json"), help="Path to column mapping JSON config")
    parser.add_argument("--output-dir", type=str, default=str(project_root / "data" / "processed"), help="Output directory for processed CSV")
    parser.add_argument("--reports-dir", type=str, default=str(project_root / "reports"), help="Output directory for cleaning reports")
    args = parser.parse_args()

    print("=" * 65)
    print(" VARTA - SPRINT 1.2 DATA PREPROCESSING PIPELINE")
    print("=" * 65)

    if args.data_path:
        data_path = args.data_path
    else:
        data_path = find_default_dataset(str(project_root / "data"))

    print(f"\n[1/2] Initializing Pipeline...")
    print(f"      Raw Dataset: {data_path}")
    print(f"      Config Path: {args.config_path}")
    print(f"      Output Dir : {args.output_dir}")
    print(f"      Reports Dir: {args.reports_dir}")

    pipeline = PreprocessingPipeline(
        raw_data_path=data_path,
        config_path=args.config_path,
        output_dir=args.output_dir,
        reports_dir=args.reports_dir
    )

    print("\n[2/2] Running Preprocessing Steps...")
    output_file, stats = pipeline.run_pipeline()

    print("\n" + "=" * 65)
    print(" SPRINT 1.2 PREPROCESSING COMPLETE - DELIVERABLES GENERATED:")
    print("=" * 65)
    print(f"  [OK] Processed Dataset : {output_file}")
    print(f"  [OK] Preprocessing Report : {os.path.join(args.reports_dir, 'preprocessing_report.md')}")
    print(f"  [OK] Cleaning Statistics  : {os.path.join(args.reports_dir, 'cleaning_statistics.md')}")
    print(f"\n  Summary: {stats['initial_rows']:,} raw rows -> {stats['final_rows']:,} cleaned rows | {stats['initial_cols']} raw cols -> {stats['final_cols']} cleaned cols")
    print("=" * 65)

if __name__ == "__main__":
    main()
