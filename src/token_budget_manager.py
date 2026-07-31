from typing import List, Dict, Any, Tuple
from src.token_counters import BaseTokenCounter, get_token_counter

class TokenBudgetManager:
    """
    Token Budget Manager for LLM Context Windows:
    - Uses pluggable BaseTokenCounter strategy interface
    - Enforces maximum context token budget (max_context_tokens)
    - Packs prioritized context blocks into token window
    - Tracks token utilization percentage and overflow dropped blocks
    """

    def __init__(
        self,
        max_context_tokens: int = 2048,
        token_counter: BaseTokenCounter = None,
        allow_partial_truncation: bool = True
    ):
        self.max_context_tokens = max_context_tokens
        self.token_counter = token_counter if token_counter else get_token_counter("heuristic")
        self.allow_partial_truncation = allow_partial_truncation

    def fit_to_budget(self, context_blocks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, float]:
        if not context_blocks:
            return [], [], 0, 0.0

        packed = []
        dropped = []
        current_tokens = 0

        for block in context_blocks:
            title = block.get("title", "") or ""
            content = block.get("content", "") or ""
            text_repr = f"Title: {title}\nContent: {content}"

            block_tokens = self.token_counter.count_tokens(text_repr)

            if current_tokens + block_tokens <= self.max_context_tokens:
                block["token_count"] = block_tokens
                packed.append(block)
                current_tokens += block_tokens
            else:
                remaining_tokens = self.max_context_tokens - current_tokens
                if self.allow_partial_truncation and remaining_tokens >= 50:
                    # Truncate content to fit remaining budget
                    approx_chars = remaining_tokens * 4
                    truncated_content = content[:approx_chars] + "... [Truncated]"
                    truncated_block = dict(block)
                    truncated_block["content"] = truncated_content
                    truncated_block["token_count"] = remaining_tokens
                    truncated_block["is_truncated"] = True

                    packed.append(truncated_block)
                    current_tokens += remaining_tokens
                else:
                    dropped.append(block)

        utilization_pct = round((current_tokens / self.max_context_tokens) * 100.0, 2)
        return packed, dropped, current_tokens, utilization_pct
