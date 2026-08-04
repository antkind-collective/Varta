import re
from typing import List, Dict, Any, Optional
from src.context_resolver import ContextResolver
from src.llm_adapter import BaseLLMAdapter

class QueryRewriter:
    """
    Query Rewriter Component for VARTA Conversational Assistant.
    Translates contextual follow-up user queries into self-contained standalone search queries
    using ContextResolver before passing them to the RAG retrieval engine.
    Bypasses query rewriting for tool requests (calculator, system info, memory tool).
    """

    TOOL_QUERY_PATTERNS = [
        r"^\s*(?:calculate|compute|what is|find|eval)?\s*\(?\s*\d+(?:\.\d+)?\s*[%+\-*/]\s*.+$",
        r"\d+\s*%\s*of\s*\d+",
        r"^\s*\d+\s*[\+\-\*\/]\s*\d+\s*$",
        r"\b(system status|system info|active model|what model|token budget|runtime environment)\b",
        r"\b(conversation history|previous questions|show history|chat history)\b",
        r"\b(search document metadata|find documents about|list document titles)\b"
    ]

    def __init__(self, context_resolver: Optional[ContextResolver] = None, llm_adapter: Optional[BaseLLMAdapter] = None):
        self.context_resolver = context_resolver if context_resolver else ContextResolver(llm_adapter=llm_adapter)

    def rewrite_query(self, query: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Processes query against session history.
        Bypasses memory rewriting if the query is a tool query.
        Returns dictionary containing:
        - original_query
        - rewritten_query
        - memory_used (True if context was applied to rewrite query)
        - resolution_method ("first_turn", "rule_based", "llm", "tool_bypass", "none")
        """
        clean_query = query.strip()
        if not clean_query:
            return {
                "original_query": query,
                "rewritten_query": query,
                "memory_used": False,
                "resolution_method": "none"
            }

        # 1. Bypass memory rewriting for tool queries (Calculator, System Info, Memory Tool, Document Search)
        if self._is_tool_query(clean_query):
            return {
                "original_query": clean_query,
                "rewritten_query": clean_query,
                "memory_used": False,
                "resolution_method": "tool_bypass"
            }

        # 2. Perform Context Resolution for RAG Queries
        needs_rewrite, resolved_query, method = self.context_resolver.resolve_context(clean_query, history)

        return {
            "original_query": clean_query,
            "rewritten_query": resolved_query if needs_rewrite else clean_query,
            "memory_used": needs_rewrite,
            "resolution_method": method
        }

    def _is_tool_query(self, query: str) -> bool:
        """Determines if a query targets a non-RAG tool and should bypass memory resolution."""
        q_lower = query.lower()
        return any(re.search(pat, q_lower, re.IGNORECASE) for pat in self.TOOL_QUERY_PATTERNS)
