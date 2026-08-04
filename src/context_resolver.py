import re
from typing import List, Dict, Any, Tuple, Optional
from src.llm_adapter import BaseLLMAdapter, MockLLMAdapter

class ContextResolver:
    """
    Determines whether a user query requires context resolution from prior turns,
    and resolves ambiguous follow-up queries into complete standalone queries.
    
    Implements a hybrid approach:
    1. Local rule-based resolution for pronoun substitution, entity carry-over, and short follow-up phrases (0 token overhead, low latency).
    2. LLM fallback resolution for complex or ambiguous multi-turn queries.
    """

    ENGLISH_PRONOUNS = {r"\bits\b", r"\bit\b", r"\bthis\b", r"\bthat\b", r"\bthere\b", r"\bthey\b", r"\bthem\b", r"\btheir\b"}
    HINDI_PRONOUNS = {r"\bउसका\b", r"\bउसकी\b", r"\bउसके\b", r"\bवह\b", r"\bवहाँ\b", r"\bइसकी\b", r"\bइसके\b", r"\bइन्हें\b"}

    def __init__(self, llm_adapter: Optional[BaseLLMAdapter] = None):
        self.llm_adapter = llm_adapter if llm_adapter else MockLLMAdapter()

    def resolve_context(self, query: str, history: List[Dict[str, Any]]) -> Tuple[bool, str, str]:
        """
        Main entry point for resolving context.
        Returns: (needs_rewrite: bool, resolved_query: str, resolution_method: str)
        """
        clean_query = query.strip()
        if not history:
            return False, clean_query, "first_turn"

        last_turn = history[-1]
        prev_user = last_turn.get("user_query", "").strip()
        prev_asst = last_turn.get("assistant_response", "").strip()

        # 1. Attempt Rule-Based Resolution (Fast Path)
        rule_success, rule_query = self._try_rule_based_resolution(clean_query, prev_user, prev_asst)
        if rule_success:
            return True, rule_query, "rule_based"

        # 2. Check if query is already completely standalone (no pronouns, contains substantive query structure)
        if self._is_already_standalone(clean_query, prev_user):
            return False, clean_query, "none"

        # 3. LLM Fallback Resolution for ambiguous cases
        llm_success, llm_query = self._llm_resolution(clean_query, history)
        if llm_success and llm_query.lower() != clean_query.lower():
            return True, llm_query, "llm"

        return False, clean_query, "none"

    def _try_rule_based_resolution(self, query: str, prev_user: str, prev_asst: str) -> Tuple[bool, str]:
        """
        Applies deterministic pattern matching and entity carry-over rules.
        """
        q_lower = query.lower()
        p_user_lower = prev_user.lower()

        # Extract primary entity/topic from previous user query
        prev_entity = self._extract_main_subject(prev_user)

        # Rule Case 1: "What about X?" / "How about X?" / "And X?"
        # Example: Prev: "Tell me about Bihar floods." | Query: "What about Patna?"
        # Result: "What about floods in Patna, Bihar?"
        match_about = re.match(r"^(what about|how about|and|tell me about)\s+(.+)$", query, re.IGNORECASE)
        if match_about:
            target_x = match_about.group(2).strip(" ?.")
            if prev_entity and target_x.lower() not in prev_entity.lower():
                # Carry over context topic from prev_user
                if "flood" in p_user_lower or "बाढ़" in prev_user:
                    resolved = f"What is the flood situation in {target_x}, {prev_entity}?"
                else:
                    resolved = f"Tell me about {target_x} regarding {prev_entity}."
                return True, resolved

        # Rule Case 1 (Hindi): "X का क्या हाल है?" / "X के बारे में?" / "X की स्थिति?"
        # Example: Prev: "गोरखपुर में बाढ़ की स्थिति?" | Query: "राप्ती नदी का क्या हाल है?"
        if re.search(r"(का क्या हाल है|के बारे में|की स्थिति|का जलस्तर)", query) and ("बाढ़" in prev_user or "गोरखपुर" in prev_user or "बिहार" in prev_user):
            if prev_entity and prev_entity not in query:
                resolved = f"{prev_entity} में {query}"
                return True, resolved

        # Rule Case 2: English Pronouns ("its", "it", "there")
        # Example: Prev: "Tell me about Rapti river." | Query: "What is its current water level?"
        # Result: "What is the current water level of Rapti river?"
        for pronoun_pat in self.ENGLISH_PRONOUNS:
            if re.search(pronoun_pat, q_lower):
                if prev_entity:
                    # Replace pronoun with entity
                    resolved = re.sub(pronoun_pat, prev_entity, query, flags=re.IGNORECASE)
                    return True, resolved

        # Rule Case 3: Hindi Pronouns ("उसका", "उसकी", "वहाँ", "इसकी")
        for pronoun_pat in self.HINDI_PRONOUNS:
            if re.search(pronoun_pat, query):
                if prev_entity:
                    resolved = re.sub(pronoun_pat, prev_entity, query)
                    return True, resolved

        # Rule Case 4: Short ellipsis/incomplete phrase (< 4 words)
        words = query.split()
        if len(words) <= 3 and prev_entity and prev_entity.lower() not in q_lower:
            if "flood" in p_user_lower or "बाढ़" in prev_user:
                resolved = f"{query} for {prev_entity} flood" if not re.search(r"[\u0900-\u097F]", query) else f"{prev_entity} {query}"
                return True, resolved

        return False, query

    def _extract_main_subject(self, text: str) -> str:
        """
        Extracts the main subject/entity from text (e.g. 'Bihar', 'Patna', 'Rapti river', 'Gorakhpur').
        """
        # Remove common preamble phrases
        cleaned = re.sub(r"^(tell me about|what is the|update on|what about|status of|info on)\s+", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+(floods?|situation|status|update|details|report|\?|\.)$", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()
        return cleaned if cleaned else text

    def _is_already_standalone(self, query: str, prev_user: str) -> bool:
        """
        Returns True if the query appears self-contained without needing resolution.
        """
        words = query.split()
        # If query is long (> 8 words) and contains no pronouns, likely standalone
        if len(words) >= 8:
            has_pronoun = any(re.search(p, query, re.IGNORECASE) for p in self.ENGLISH_PRONOUNS | self.HINDI_PRONOUNS)
            if not has_pronoun:
                return True
        return False

    def _llm_resolution(self, query: str, history: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Uses LLM Adapter as fallback to rewrite ambiguous queries into standalone search queries.
        """
        history_snippet = []
        for turn in history[-2:]:  # look at last 2 turns
            history_snippet.append(f"User: {turn['user_query']}")
            history_snippet.append(f"Assistant: {turn['assistant_response'][:150]}...")
        
        hist_text = "\n".join(history_snippet)
        prompt = (
            "System: You are a query rewriting assistant. Given the conversation history, rewrite the user's latest follow-up question "
            "into a complete, self-contained standalone search query. Do NOT answer the question. Output ONLY the rewritten standalone query.\n\n"
            f"Conversation History:\n{hist_text}\n\n"
            f"Follow-up Question: {query}\n\n"
            "Standalone Query:"
        )

        try:
            llm_resp = self.llm_adapter.generate(prompt)
            rewritten = llm_resp.get("text", "").strip()
            # Clean quotes if LLM wraps response in quotes
            rewritten = re.sub(r'^["\']|["\']$', '', rewritten).strip()
            if rewritten and rewritten.lower() != query.lower():
                return True, rewritten
        except Exception:
            pass

        return False, query
