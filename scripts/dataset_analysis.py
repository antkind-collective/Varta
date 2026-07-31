#!/usr/bin/env python3
"""
VARTA Phase 1 - Sprint 1.1: Dataset Discovery & Analysis CLI Script.

Executes generic, dynamic dataset discovery, schema classification, data quality assessment,
text profiling, and generates comprehensive markdown reports.
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.dataset_loader import DatasetLoader
from src.schema_classifier import SchemaClassifier
from src.quality_assessor import QualityAssessor
from src.text_analyzer import TextAnalyzer
from src.report_generator import ReportGenerator

def find_default_dataset(data_dir: str) -> str:
    """Automatically locates the first CSV dataset inside data_dir."""
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Data directory '{data_dir}' does not exist.")
    
    csv_files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    if not csv_files:
        raise FileNotFoundError(f"No CSV dataset found inside '{data_dir}'.")
    
    return os.path.join(data_dir, csv_files[0])

def main():
    parser = argparse.ArgumentParser(description="VARTA Dataset Discovery and Analysis Tool")
    parser.add_argument("--data-path", type=str, help="Path to input CSV dataset. If omitted, auto-discovers in data/")
    parser.add_argument("--config-path", type=str, default=str(project_root / "config" / "analysis_config.json"), help="Path to analysis configuration JSON")
    parser.add_argument("--output-dir", type=str, default=str(project_root / "reports"), help="Output directory for generated markdown reports")
    args = parser.parse_args()

    print("=" * 65)
    print(" VARTA - SPRINT 1.1 DATASET DISCOVERY & ANALYSIS")
    print("=" * 65)

    # 1. Locate Dataset
    if args.data_path:
        dataset_path = args.data_path
    else:
        dataset_path = find_default_dataset(str(project_root / "data"))

    print(f"\n[1/5] Loading Dataset: {dataset_path}")
    loader = DatasetLoader(dataset_path)
    df, meta_metrics = loader.load_dataset()

    print(f"      Rows: {meta_metrics['row_count']:,} | Columns: {meta_metrics['column_count']} | Memory: {meta_metrics['memory_usage_mb']} MB")

    # 2. Load Configuration
    config_path = args.config_path
    if not os.path.exists(config_path):
        print(f"Warning: Configuration file not found at {config_path}. Using default parameters.")
        config = {}
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    # 3. Schema Classification
    print("\n[2/5] Performing Dynamic Schema Classification...")
    classifier = SchemaClassifier(config)
    schema_classifications = classifier.classify_columns(df)
    
    cat_summary = {}
    for sc in schema_classifications:
        cat_summary[sc["category"]] = cat_summary.get(sc["category"], 0) + 1
    
    print("      Classified Categories:")
    for cat, count in cat_summary.items():
        print(f"      - {cat}: {count} columns")

    # 4. Data Quality Assessment
    print("\n[3/5] Performing Data Quality Assessment...")
    assessor = QualityAssessor(schema_classifications)
    quality_results = assessor.assess_quality(df)

    print(f"      Full Duplicate Rows: {quality_results['duplicate_rows_count']:,} ({quality_results['duplicate_rows_pct']}%)")
    print(f"      Unnamed / Ghost Columns: {quality_results['unnamed_empty_cols_count']}")

    # 5. Text Analysis
    print("\n[4/5] Performing Text Profiling & Noise Detection...")
    text_cols = [c["column"] for c in schema_classifications if c["category"] == "Text"]
    print(f"      Text Columns Identified: {text_cols}")
    
    text_analyzer = TextAnalyzer(config)
    text_results = text_analyzer.analyze_text_columns(df, text_cols)

    for tr in text_results:
        print(f"      - Column '{tr['column']}': Avg Length {tr['char_stats']['mean']} chars | Short: {tr['threshold_counts']['short']} | Long: {tr['threshold_counts']['long']}")

    # 6. Report Generation
    print(f"\n[5/5] Generating Markdown Reports in: {args.output_dir}")
    generator = ReportGenerator(args.output_dir)
    generated_files = generator.generate_all_reports(meta_metrics, schema_classifications, quality_results, text_results)

    print("\n" + "=" * 65)
    print(" SPRINT 1.1 ANALYSIS COMPLETE - REPORTS GENERATED:")
    print("=" * 65)
    for report_name, abs_path in generated_files.items():
        print(f"  [OK] {report_name}.md -> {abs_path}")
    print("=" * 65)

if __name__ == "__main__":
    main()
