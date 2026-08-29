import re
from typing import List, Dict, Any

class QueryDecomposer:
    """
    Query Decomposer for VARTA Agentic Planner.
    Splits complex, multi-part, or comparative queries into concise, grammatically correct,
    and search-optimized atomic sub-queries.
    """

    COMPARISON_REGEX_EN = [
        r"^compare\s+(?:the\s+)?(?:latest\s+)?(?:flood\s+impacts?|floods?|flood\s+situations?|impacts?|damages?|situations?|status|relief\s+operations?|rescue\s+operations?)?\s*(?:in|of|between)?\s*(.*?)\s+(?:and|with|to)\s+(.*?)(?:\s+floods|\s+situations?|\s+impacts?|\s+during|\s+in|\.|\?|$)",
        r"comparison\s+(?:of|between)\s+(?:the\s+)?(?:flood\s+impacts?|floods?|situations?|impacts?)?\s*(?:in|of)?\s*(.*?)\s+and\s+(.*?)(?:\.|\?|$)",
        r"(.*?)\s+(?:versus|vs\.?)\s+(.*?)(?:\.|\?|$)"
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

    def _extract_comparison_topic(self, query: str) -> str:
        """Extracts appropriate search prefix topic from comparative query."""
        q_lower = query.lower()
        if "flood impact" in q_lower or "impact" in q_lower:
            return "Flood impacts in"
        elif "rescue" in q_lower or "relief" in q_lower:
            return "Relief and rescue operations in"
        elif "casualt" in q_lower or "death" in q_lower:
            return "Casualties and damage in"
        elif "water level" in q_lower or "river" in q_lower:
            return "River water levels and flood status in"
        elif "flood" in q_lower or "बाढ़" in query:
            return "Flood situation in"
        return "Information on"

    def _decompose_comparison(self, query: str) -> List[Dict[str, Any]]:
        """
        Extracts comparative subjects and generates clean, concise standalone sub-queries.
        """
        q_lower = query.lower()
        prefix = self._extract_comparison_topic(query)

        # Try English Comparative Patterns
        for pat in self.COMPARISON_REGEX_EN:
            match = re.search(pat, query, re.IGNORECASE)
            if match:
                raw1 = match.group(1).strip()
                raw2 = match.group(2).strip()

                entity1 = self._clean_entity_name(raw1)
                entity2 = self._clean_entity_name(raw2)

                if entity1 and entity2 and entity1.lower() != entity2.lower():
                    sub1 = f"{prefix} {entity1}"
                    sub2 = f"{prefix} {entity2}"

                    return [
                        {"type": "retrieve", "query": sub1, "target": entity1},
                        {"type": "retrieve", "query": sub2, "target": entity2},
                        {"type": "compare"}
                    ]

        # Try Hindi Comparative Patterns
        for pat in self.COMPARISON_REGEX_HI:
            match = re.search(pat, query)
            if match:
                raw1 = match.group(1).strip()
                raw2 = match.group(2).strip()

                entity1 = self._clean_entity_name(raw1)
                entity2 = self._clean_entity_name(raw2)

                if entity1 and entity2 and entity1 != entity2:
                    sub1 = f"{entity1} में बाढ़ की स्थिति" if "बाढ़" in query else f"{entity1} की जानकारी"
                    sub2 = f"{entity2} में बाढ़ की स्थिति" if "बाढ़" in query else f"{entity2} की जानकारी"

                    return [
                        {"type": "retrieve", "query": sub1, "target": entity1},
                        {"type": "retrieve", "query": sub2, "target": entity2},
                        {"type": "compare"}
                    ]

        # Fallback splitting by 'vs' / 'versus' ONLY if explicit comparison targets exist
        parts = re.split(r"\b(vs|versus)\b", query, flags=re.IGNORECASE)
        if len(parts) >= 3:
            raw1 = parts[0].strip()
            raw2 = parts[2].strip()
            e1 = self._clean_entity_name(raw1)
            e2 = self._clean_entity_name(raw2)
            if e1 and e2 and e1.lower() != e2.lower():
                return [
                    {"type": "retrieve", "query": f"{prefix} {e1}", "target": e1},
                    {"type": "retrieve", "query": f"{prefix} {e2}", "target": e2},
                    {"type": "compare"}
                ]

        return [{"type": "retrieve", "query": query}]

    def _clean_entity_name(self, text: str) -> str:
        """Strips common prefix/suffix noise to extract clean entity/location names."""
        cleaned = text.strip()
        for _ in range(3):
            cleaned = re.sub(r"^(compare|the|latest|flood|floods|impacts?|damages?|situations?|status|relief|rescue|of|in|at|between|about)\s+", "", cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"\s+(floods?|situations?|status|impacts?|damages?|during|in|at|\.|\?)$", "", cleaned, flags=re.IGNORECASE).strip()

        # Reject full sentences, complex clauses, or long text
        if len(cleaned) > 35 or len(cleaned.split()) > 4:
            return ""
        if any(w in cleaned.lower().split() for w in ["is", "are", "were", "was", "how", "why", "describe", "experienced", "mentioned", "talk", "difference", "between"]):
            return ""

        return cleaned.title() if cleaned.islower() or cleaned.isupper() else (cleaned if cleaned else "")

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
