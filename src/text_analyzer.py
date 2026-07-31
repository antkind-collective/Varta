import pandas as pd
import numpy as np
import re
from typing import Dict, Any, List

class TextAnalyzer:
    """
    Analyzes text columns for length distribution and structural noise:
    - Min, Max, Mean, Median character and word lengths
    - Blank records, short records (< threshold), long records (> threshold)
    - HTML tags, URLs, Emojis, line breaks, extra whitespace, non-ASCII/encoding quirks
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.short_thresh = config.get("short_text_threshold", 20)
        self.long_thresh = config.get("long_text_threshold", 1000)
        self.patterns = {
            "html_tags": re.compile(config["regex_patterns"]["html_tags"]),
            "urls": re.compile(config["regex_patterns"]["urls"], re.IGNORECASE),
            "emojis": re.compile(config["regex_patterns"]["emojis"]),
            "line_breaks": re.compile(config["regex_patterns"]["line_breaks"]),
            "extra_whitespace": re.compile(config["regex_patterns"]["extra_whitespace"]),
            "non_printable": re.compile(config["regex_patterns"]["non_printable"])
        }

    def analyze_text_columns(self, df: pd.DataFrame, text_columns: List[str]) -> List[Dict[str, Any]]:
        results = []

        for col in text_columns:
            if col not in df.columns:
                continue

            series = df[col].dropna().astype(str)
            total_records = len(df)
            non_null_records = len(series)

            if non_null_records == 0:
                results.append({
                    "column": col,
                    "record_count": 0,
                    "min_len": 0, "max_len": 0, "mean_len": 0.0, "median_len": 0.0,
                    "min_words": 0, "max_words": 0, "mean_words": 0.0, "median_words": 0.0,
                    "blank_count": total_records,
                    "short_count": 0, "long_count": 0,
                    "noise_counts": {k: 0 for k in self.patterns.keys()}
                })
                continue

            # Length calculations
            char_lens = series.str.len()
            word_counts = series.str.split().str.len()

            min_len = int(char_lens.min())
            max_len = int(char_lens.max())
            mean_len = round(float(char_lens.mean()), 2)
            median_len = round(float(char_lens.median()), 2)

            min_words = int(word_counts.min())
            max_words = int(word_counts.max())
            mean_words = round(float(word_counts.mean()), 2)
            median_words = round(float(word_counts.median()), 2)

            blank_count = int((series.str.strip() == "").sum()) + (total_records - non_null_records)
            short_count = int((char_lens < self.short_thresh).sum())
            long_count = int((char_lens > self.long_thresh).sum())

            # Noise Detection
            noise_counts = {}
            for name, pattern in self.patterns.items():
                match_count = int(series.apply(lambda text: bool(pattern.search(text))).sum())
                noise_counts[name] = match_count

            # Multi-script / Non-ASCII detection
            non_ascii_count = int(series.apply(lambda text: any(ord(c) > 127 for c in text)).sum())
            noise_counts["non_ascii_or_multilingual"] = non_ascii_count

            results.append({
                "column": col,
                "total_records": total_records,
                "non_null_records": non_null_records,
                "char_stats": {
                    "min": min_len,
                    "max": max_len,
                    "mean": mean_len,
                    "median": median_len
                },
                "word_stats": {
                    "min": min_words,
                    "max": max_words,
                    "mean": mean_words,
                    "median": median_words
                },
                "threshold_counts": {
                    "blank": blank_count,
                    "short": short_count,
                    "short_threshold": self.short_thresh,
                    "long": long_count,
                    "long_threshold": self.long_thresh
                },
                "noise_counts": noise_counts
            })

        return results
