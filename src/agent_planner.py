import re
from typing import List, Dict, Any, Optional
from src.execution_plan import ExecutionPlan
from src.query_decomposer import QueryDecomposer
from src.llm_adapter import BaseLLMAdapter, MockLLMAdapter

class AgentPlanner:
    """
    Agentic Planning Layer for VARTA Assistant.
    Analyzes user query intent, classifies plan type (direct, followup, comparison, multi_step, summarization,
    calculator, system_info, conversation_memory, document_search, clarification),
    invokes QueryDecomposer for complex queries, and returns a structured ExecutionPlan.
    """

    COMPARISON_KEYWORDS = {"compare", "comparison", "versus", "vs", "तुलना"}
    SUMMARIZATION_KEYWORDS = {"summarize", "summary", "overview", "overall status", "सारंश", "संक्षेप", "विवरण"}
    SYSTEM_INFO_KEYWORDS = {
        "system status", "system info", "active model", "what model", "system information",
        "token budget", "runtime environment"
    }
    META_CITATION_PATTERNS = [
        r"why\b.*\b(?:not\s+giving|no|missing|without|don't\s+give|didn't\s+give|not\s+showing|not\s+providing)\b.*\b(?:urls?|links?|sources?|citations?|references?)\b",
        r"why\b.*\b(?:doc\s*ids?|document\s*ids?)\b.*\b(?:instead|no\s+urls?|without\s+urls?|only)\b",
        r"why\b.*\b(?:only|showing|displaying)\b.*\b(?:doc\s*ids?|document\s*ids?)\b",
        r"why\b.*\b(?:some|any)\b.*\b(?:references?|citations?|sources?)\b.*\b(?:no|without|missing|have\s+no)\b.*\b(?:urls?|links?)\b",
        r"why\s+are\s+there\s+no\s+urls?\b",
        r"how\b.*\b(?:citations?|references?|sources?)\b.*\b(?:work|handled|generated|managed)\b",
        r"where\b.*\b(?:source\s+urls?|citations?|references?)\b",
        r"\b(?:what\s+is\s+varta|what\s+can\s+you\s+do|who\s+are\s+you|help\s+with\s+varta)\b"
    ]
    MEMORY_TOOL_KEYWORDS = {"conversation history", "previous questions", "what was my first question", "show history", "chat history"}
    DOC_SEARCH_KEYWORDS = {"search document metadata", "find documents about", "list document titles", "document search"}

    def __init__(self, query_decomposer: Optional[QueryDecomposer] = None, llm_adapter: Optional[BaseLLMAdapter] = None):
        self.query_decomposer = query_decomposer if query_decomposer else QueryDecomposer()
        self.llm_adapter = llm_adapter if llm_adapter else MockLLMAdapter()

    def create_plan(
        self,
        query: str,
        rewritten_query: str,
        memory_used: bool = False,
        history_count: int = 0
    ) -> ExecutionPlan:
        """
        Main entry point for generating an ExecutionPlan from user input.
        """
        clean_q = query.strip()
        clean_rw = rewritten_query.strip()

        # 1. Check Clarification Required / Invalid Query
        if not clean_q:
            return ExecutionPlan(
                plan_type="clarification",
                steps=[{"type": "clarify"}],
                original_query=query,
                rewritten_query=rewritten_query,
                reasoning="Empty input query requires user clarification."
            )

        combined_text = f"{clean_q} {clean_rw}".lower()

        # 2. Check Calculator Intent (arithmetic expressions / percentages)
        if self._is_calculator_query(clean_q):
            return ExecutionPlan(
                plan_type="calculator",
                steps=[{"type": "tool_call", "tool": "calculator", "expression": clean_q}],
                original_query=clean_q,
                rewritten_query=clean_rw,
                reasoning="Mathematical calculation query detected requiring CalculatorTool."
            )

        # 3. Check System Info & Meta Explanation Intent (Citations / URLs / VARTA identity)
        is_sys_info = any(kw in combined_text for kw in self.SYSTEM_INFO_KEYWORDS)
        is_meta_query = any(re.search(pat, combined_text, re.IGNORECASE) for pat in self.META_CITATION_PATTERNS)
        if is_sys_info or is_meta_query:
            return ExecutionPlan(
                plan_type="system_info",
                steps=[{"type": "tool_call", "tool": "system_info", "query": clean_q}],
                original_query=clean_q,
                rewritten_query=clean_rw,
                reasoning="System status or meta-explanation query detected requiring SystemInfoTool."
            )

        # 4. Check Conversation Memory Intent
        if any(kw in combined_text for kw in self.MEMORY_TOOL_KEYWORDS):
            return ExecutionPlan(
                plan_type="conversation_memory",
                steps=[{"type": "tool_call", "tool": "conversation_memory"}],
                original_query=clean_q,
                rewritten_query=clean_rw,
                reasoning="Conversation history query detected requiring ConversationMemoryTool."
            )

        # 5. Check Document Search Metadata Intent
        if any(kw in combined_text for kw in self.DOC_SEARCH_KEYWORDS):
            return ExecutionPlan(
                plan_type="document_search",
                steps=[{"type": "tool_call", "tool": "document_search", "query": clean_q}],
                original_query=clean_q,
                rewritten_query=clean_rw,
                reasoning="Document metadata search detected requiring DocumentSearchTool."
            )

        # 6. Check Comparison Query
        is_comparison = any(re.search(r"\b" + re.escape(kw) + r"\b", clean_q.lower()) for kw in self.COMPARISON_KEYWORDS)
        if is_comparison or (" और " in clean_q and "तुलना" in clean_q) or (" compare " in f" {clean_q.lower()} "):
            steps = self.query_decomposer.decompose_query(clean_rw, plan_type="comparison")
            retrieval_steps = [s for s in steps if s.get("type") == "retrieve"]
            if len(retrieval_steps) > 1:
                return ExecutionPlan(
                    plan_type="comparison",
                    steps=steps,
                    original_query=clean_q,
                    rewritten_query=clean_rw,
                    reasoning="Comparative query detected requiring separate retrievals for comparison."
                )

        # 7. Check Multi-Step Query
        is_multistep = any(conj in combined_text for conj in ["and also", "as well as", "साथ ही"])
        if is_multistep:
            steps = self.query_decomposer.decompose_query(clean_rw, plan_type="multi_step")
            if len(steps) > 1:
                return ExecutionPlan(
                    plan_type="multi_step",
                    steps=steps,
                    original_query=clean_q,
                    rewritten_query=clean_rw,
                    reasoning="Multi-part query detected requiring multi-step retrieval."
                )

        # 8. Check Summarization Query
        is_summarization = any(re.search(r"\b" + re.escape(kw) + r"\b", combined_text) for kw in self.SUMMARIZATION_KEYWORDS)
        if is_summarization:
            return ExecutionPlan(
                plan_type="summarization",
                steps=[
                    {"type": "retrieve", "query": clean_rw},
                    {"type": "summarize"}
                ],
                original_query=clean_q,
                rewritten_query=clean_rw,
                reasoning="Broad overview/summarization request detected."
            )

        # 9. Check Follow-Up Query
        if memory_used:
            return ExecutionPlan(
                plan_type="followup",
                steps=[{"type": "retrieve", "query": clean_rw}],
                original_query=clean_q,
                rewritten_query=clean_rw,
                reasoning="Contextual follow-up resolved using conversation memory."
            )

        # 10. Default Direct Single Retrieval
        return ExecutionPlan(
            plan_type="direct",
            steps=[{"type": "retrieve", "query": clean_rw}],
            original_query=clean_q,
            rewritten_query=clean_rw,
            reasoning="Direct factual query requiring single semantic retrieval."
        )

    def _is_calculator_query(self, query: str) -> bool:
        """Determines if a query is a mathematical expression or calculation request."""
        clean = query.strip()
        # Direct math operator patterns (e.g. 25 * 19, (250 + 800) / 7, 12% of 800)
        if re.search(r"^\s*(?:calculate|compute|what is|find|eval)?\s*\(?\s*\d+(?:\.\d+)?\s*[%+\-*/]\s*.+$", clean, re.IGNORECASE):
            return True
        if re.search(r"\d+\s*%\s*of\s*\d+", clean, re.IGNORECASE):
            return True
        if re.match(r"^\s*calculate\s+.+$", clean, re.IGNORECASE) and any(c in clean for c in "+-*/%"):
            return True
        return False
