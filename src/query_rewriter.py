from typing import List, Dict, Any, Optional
from src.context_resolver import ContextResolver
from src.llm_adapter import BaseLLMAdapter

class QueryRewriter:
    """
    Query Rewriter Component for VARTA Conversational Assistant.
    Translates contextual follow-up user queries into self-contained standalone search queries
    using ContextResolver before passing them to the RAG retrieval engine.
    """

    def __init__(self, context_resolver: Optional[ContextResolver] = None, llm_adapter: Optional[BaseLLMAdapter] = None):
        self.context_resolver = context_resolver if context_resolver else ContextResolver(llm_adapter=llm_adapter)

    def rewrite_query(self, query: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Processes query against session history.
        Returns dictionary containing:
        - original_query
        - rewritten_query
        - memory_used (True if context was applied to rewrite query)
        - resolution_method ("first_turn", "rule_based", "llm", "none")
        """
        clean_query = query.strip()
        if not clean_query:
            return {
                "original_query": query,
                "rewritten_query": query,
                "memory_used": False,
                "resolution_method": "none"
            }

        needs_rewrite, resolved_query, method = self.context_resolver.resolve_context(clean_query, history)

        return {
            "original_query": clean_query,
            "rewritten_query": resolved_query if needs_rewrite else clean_query,
            "memory_used": needs_rewrite,
            "resolution_method": method
        }
