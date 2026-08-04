import re
from typing import List, Dict, Any

class QueryDecomposer:
    """
    Query Decomposer for VARTA Agentic Planner.
    Splits complex, multi-part, or comparative queries into atomic sub-queries and execution steps.
    """

    COMPARISON_REGEX_EN = [
        r"compare\s+(.*?)\s+and\s+(.*?)(?:\s+floods|\s+situation|\s+during|\s+in|\.|\?|$)",
        r"comparison\s+between\s+(.*?)\s+and\s+(.*?)(?:\.|\?|$)",
        r"(.*?)\s+versus\s+(.*?)(?:\.|\?|$)"
    ]

    COMPARISON_REGEX_HI = [
        r"(.*?)\s+और\s+(.*?)\s+(?:की|में)\s+तुलना",
        r"(.*?)\s+तथा\s+(.*?)\s+की\s+तुलना"
    ]

    def decompose_query(self, query: str, plan_type: str = "comparison") -> List[Dict[str, Any]]:
        """
        Decomposes query into structured sub-query execution steps.
        """
        clean_q = query.strip()

        if plan_type == "comparison":
            return self._decompose_comparison(clean_q)
        elif plan_type == "multi_step":
            return self._decompose_multistep(clean_q)
        else:
            return [{"type": "retrieve", "query": clean_q}]

    def _decompose_comparison(self, query: str) -> List[Dict[str, Any]]:
        """
        Extracts comparative subjects and generates comparison steps.
        """
        # Try English Comparative Patterns
        for pat in self.COMPARISON_REGEX_EN:
            match = re.search(pat, query, re.IGNORECASE)
            if match:
                item1 = match.group(1).strip()
                item2 = match.group(2).strip()
                # Clean lead-ins
                item1 = re.sub(r"^(floods?|situation|status|in)\s+", "", item1, flags=re.IGNORECASE).strip()
                item2 = re.sub(r"^(floods?|situation|status|in)\s+", "", item2, flags=re.IGNORECASE).strip()
                
                sub1 = f"Flood situation in {item1}" if "flood" in query.lower() else f"Information on {item1}"
                sub2 = f"Flood situation in {item2}" if "flood" in query.lower() else f"Information on {item2}"

                return [
                    {"type": "retrieve", "query": sub1, "target": item1},
                    {"type": "retrieve", "query": sub2, "target": item2},
                    {"type": "compare"}
                ]

        # Try Hindi Comparative Patterns
        for pat in self.COMPARISON_REGEX_HI:
            match = re.search(pat, query)
            if match:
                item1 = match.group(1).strip()
                item2 = match.group(2).strip()
                item1 = re.sub(r"^(बाढ़|स्थिति|में)\s+", "", item1).strip()
                item2 = re.sub(r"^(बाढ़|स्थिति|में)\s+", "", item2).strip()

                sub1 = f"{item1} में बाढ़ की स्थिति" if "बाढ़" in query else f"{item1} की जानकारी"
                sub2 = f"{item2} में बाढ़ की स्थिति" if "बाढ़" in query else f"{item2} की जानकारी"

                return [
                    {"type": "retrieve", "query": sub1, "target": item1},
                    {"type": "retrieve", "query": sub2, "target": item2},
                    {"type": "compare"}
                ]

        # Fallback splitting by 'and' / 'और' if regex didn't match cleanly
        parts = re.split(r"\b(and|vs|versus|और|तथा)\b", query, flags=re.IGNORECASE)
        if len(parts) >= 3:
            part1 = parts[0].strip()
            part2 = parts[2].strip()
            return [
                {"type": "retrieve", "query": part1},
                {"type": "retrieve", "query": part2},
                {"type": "compare"}
            ]

        return [
            {"type": "retrieve", "query": query},
            {"type": "compare"}
        ]

    def _decompose_multistep(self, query: str) -> List[Dict[str, Any]]:
        """
        Splits multi-part questions joined by conjunctions ('and also', 'also', 'तथा', 'साथ ही').
        """
        parts = re.split(r"\b(and also|also|as well as|तथा|साथ ही)\b", query, flags=re.IGNORECASE)
        steps = []
        for p in parts:
            p_clean = p.strip()
            if p_clean and p_clean.lower() not in {"and also", "also", "as well as", "तथा", "साथ ही"}:
                steps.append({"type": "retrieve", "query": p_clean})

        if len(steps) > 1:
            steps.append({"type": "synthesize"})
            return steps

        return [{"type": "retrieve", "query": query}]
