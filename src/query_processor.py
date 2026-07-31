import re

class QueryProcessor:
    """
    Multilingual Query Preprocessing Engine for VARTA Semantic Retrieval:
    - Normalizes internal multiline breaks, tabs, and excess whitespace to single spaces.
    - Preserves English, Hindi Devanagari, Bengali, and all Unicode scripts 100%.
    - Validates non-empty input, throwing clean ValueError for empty/whitespace inputs.
    - Strips unprintable control characters (ASCII 0x00-0x1F) while retaining structure.
    """

    def process(self, query: str) -> str:
        if query is None:
            raise ValueError("Query string cannot be None.")

        # Strip unprintable control characters
        cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", str(query))

        # Collapse whitespace runs
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if not cleaned:
            raise ValueError("Query string cannot be empty or whitespace-only.")

        return cleaned
