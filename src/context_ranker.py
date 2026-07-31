from typing import List, Dict, Any

class ContextRanker:
    """
    Context Ranker & Diversity Prioritizer:
    Ranks context blocks combining Cosine Similarity scores with parent document diversity bonuses.
    """

    def rank_context_blocks(self, context_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not context_blocks:
            return []

        ranked = list(context_blocks)
        # Compute composite priority score
        for idx, block in enumerate(ranked):
            score = float(block.get("similarity_score", 0.0))
            diversity_bonus = 0.10 if idx > 0 else 0.0
            block["priority_score"] = round(score + diversity_bonus, 4)

        ranked.sort(key=lambda x: x.get("priority_score", -1.0), reverse=True)
        return ranked
