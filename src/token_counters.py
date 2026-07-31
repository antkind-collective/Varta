import math
from abc import ABC, abstractmethod

class BaseTokenCounter(ABC):
    """
    Pluggable token counting strategy interface for VARTA RAG token budget management.
    Allows seamless swapping between heuristic character counters and provider-specific tokenizers.
    """

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Returns estimated or exact token count for input text string."""
        pass


class HeuristicTokenCounter(BaseTokenCounter):
    """
    Default lightweight token counter using ~4 characters per token heuristic
    with a 10% safety margin.
    """

    def __init__(self, chars_per_token: float = 4.0, safety_margin: float = 1.10):
        self.chars_per_token = chars_per_token
        self.safety_margin = safety_margin

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        raw_tokens = len(text) / self.chars_per_token
        return max(1, math.ceil(raw_tokens * self.safety_margin))


class TiktokenTokenCounter(BaseTokenCounter):
    """
    OpenAI tiktoken tokenizer strategy wrapper.
    Falls back to HeuristicTokenCounter if tiktoken is not installed.
    """

    def __init__(self, encoding_name: str = "cl100k_base"):
        self.encoding_name = encoding_name
        try:
            import tiktoken
            self.encoding = tiktoken.get_encoding(encoding_name)
            self._available = True
        except ImportError:
            self._available = False
            self._fallback = HeuristicTokenCounter()

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if self._available:
            return len(self.encoding.encode(text))
        return self._fallback.count_tokens(text)


def get_token_counter(strategy_name: str = "heuristic") -> BaseTokenCounter:
    strategy = str(strategy_name).lower().strip()
    if strategy == "tiktoken":
        return TiktokenTokenCounter()
    return HeuristicTokenCounter()
