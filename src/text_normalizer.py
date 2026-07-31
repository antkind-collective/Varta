import re
import pandas as pd
from typing import Dict, Any, List, Tuple

class TextNormalizer:
    """
    Text normalizer module for cleaning and standardizing text content while preserving Unicode & meaning:
    - Normalizes line breaks (\r\n -> \n)
    - Collapses consecutive tabs/spaces to single space
    - Strips non-printable ASCII control characters
    - Preserves multilingual scripts (Hindi Devanagari, Bengali, English, etc.)
    - Preserves original punctuation and semantic payload without summarizing.
    """

    def __init__(self):
        # Control character regex (excluding \n and \t)
        self.control_char_pattern = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
        self.line_break_pattern = re.compile(r'\r\n|\r')
        self.consecutive_breaks_pattern = re.compile(r'\n{3,}')
        self.extra_spaces_pattern = re.compile(r'[ \t]{2,}')

    def normalize_text_string(self, text: str) -> str:
        if not text or not isinstance(text, str):
            return ""
        
        # 1. Normalize line breaks
        text = self.line_break_pattern.sub('\n', text)
        text = self.consecutive_breaks_pattern.sub('\n\n', text)
        
        # 2. Strip unprintable control characters
        text = self.control_char_pattern.sub('', text)
        
        # 3. Normalize spaces per line
        lines = [self.extra_spaces_pattern.sub(' ', line).strip() for line in text.split('\n')]
        
        # 4. Rejoin non-empty structure
        normalized = '\n'.join(lines).strip()
        return normalized

    def normalize_series(self, series: pd.Series) -> Tuple[pd.Series, int]:
        """
        Normalizes a pandas Series of text entries.
        Returns normalized series and count of modified entries.
        """
        modified_count = 0
        normalized_list = []

        for val in series:
            if pd.isna(val) or val is None:
                normalized_list.append(val)
                continue
            
            val_str = str(val)
            cleaned = self.normalize_text_string(val_str)
            if cleaned != val_str:
                modified_count += 1
            normalized_list.append(cleaned if cleaned != "" else None)

        return pd.Series(normalized_list, index=series.index, dtype="object"), modified_count
