import re
from typing import List, Dict, Any, Tuple, Optional
from src.llm_adapter import BaseLLMAdapter, MockLLMAdapter

class ContextResolver:
    """
    Determines whether a user query requires context resolution from prior turns,
    and resolves ambiguous follow-up queries into complete standalone queries.
    
    Implements a hybrid approach:
    1. Local rule-based resolution for pronoun substitution, entity carry-over, and short follow-up phrases.
    2. Explicit standalone detection to prevent independent topic changes from inheriting previous context.
    3. LLM fallback resolution for complex multi-turn queries.
    """

    ENGLISH_PRONOUNS = {r"\bits\b", r"\bit\b", r"\bthis\b", r"\bthat\b", r"\bthere\b", r"\bthey\b", r"\bthem\b", r"\btheir\b"}
    HINDI_PRONOUNS = {r"\bउसका\b", r"\bउसकी\b", r"\bउसके\b", r"\bवह\b", r"\bवहाँ\b", r"\bइसकी\b", r"\bइसके\b", r"\bइन्हें\b"}

    FOLLOWUP_PREAMBLES_EN = (r"^what about\b", r"^how about\b", r"^and\b")
    FOLLOWUP_PHRASES_HI = ("का क्या हाल है", "क्या हाल है", "के बारे में क्या", "और बताएँ")

    STANDALONE_OPENERS = (r"^tell me about\b", r"^explain\b", r"^describe\b", r"^details on\b", r"^information on\b", r"^what is\b", r"^compare\b")

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

        # 1. Check if query is ALREADY standalone (Independent Topic Change Guard)
        if self._is_already_standalone(clean_query, prev_user):
            return False, clean_query, "none"

        # 2. Attempt Rule-Based Resolution (Fast Path)
        rule_success, rule_query = self._try_rule_based_resolution(clean_query, prev_user, prev_asst)
        if rule_success:
            return True, rule_query, "rule_based"

        # 3. LLM Fallback Resolution for ambiguous cases
        llm_success, llm_query = self._llm_resolution(clean_query, history)
        if llm_success and llm_query.lower() != clean_query.lower():
            return True, llm_query, "llm"

        return False, clean_query, "none"

    def _is_already_standalone(self, query: str, prev_user: str) -> bool:
        """
        Determines if a query is complete and independent without needing context from previous turns.
        """
        q_lower = query.lower()

        # 1. Check for explicit pronouns in English or Hindi -> NOT standalone (requires follow-up resolution)
        has_pronoun = any(re.search(p, q_lower) for p in self.ENGLISH_PRONOUNS | self.HINDI_PRONOUNS)
        if has_pronoun:
            return False

        # 2. Check if query starts with explicit standalone opener like "Tell me about Assam floods."
        starts_with_standalone_opener = any(re.search(op, q_lower) for op in self.STANDALONE_OPENERS)

        # 3. Check if query contains explicit follow-up preambles or continuation phrases -> NOT standalone
        has_followup_preamble = any(re.search(p, q_lower) for p in self.FOLLOWUP_PREAMBLES_EN)
        if has_followup_preamble:
            return False

        has_followup_phrase_hi = any(p in query for p in self.FOLLOWUP_PHRASES_HI)
        if has_followup_phrase_hi:
            return False

        # 4. If query starts with standalone opener and has no pronouns/follow-up preambles -> STANDALONE
        if starts_with_standalone_opener:
            return True

        # 5. Check if query is a short fragment (< 4 words) missing a main subject -> NOT standalone
        words = query.split()
        if len(words) <= 3 and not self._contains_specific_subject(query):
            return False

        # 6. Independent topic change guard:
        # If query starts with a brand new location or independent entity (e.g. "गोरखपुर में बाढ़ की स्थिति?")
        prev_subject = self._extract_main_subject(prev_user).lower()
        curr_subject = self._extract_main_subject(query).lower()

        if curr_subject and prev_subject and curr_subject != prev_subject and curr_subject not in prev_subject:
            return True

        # Default: if query has >= 4 words and no pronouns or follow-up markers, treat as standalone
        if len(words) >= 4:
            return True

        return False

    def _try_rule_based_resolution(self, query: str, prev_user: str, prev_asst: str) -> Tuple[bool, str]:
        """
        Applies deterministic pattern matching and entity carry-over rules for genuine follow-ups.
        """
        q_lower = query.lower()
        p_user_lower = prev_user.lower()

        prev_entity = self._extract_main_subject(prev_user)

        # Rule Case 1: "What about X?" / "How about X?" / "And X?"
        # Example: Prev: "Tell me about Bihar floods." | Query: "What about Patna?" -> "What is the flood situation in Patna, Bihar?"
        match_about = re.match(r"^(what about|how about|and)\s+(.+)$", query, re.IGNORECASE)
        if match_about:
            target_x = match_about.group(2).strip(" ?.")
            if prev_entity and target_x.lower() not in prev_entity.lower():
                if "flood" in p_user_lower or "बाढ़" in prev_user:
                    resolved = f"What is the flood situation in {target_x}, {prev_entity}?"
                else:
                    resolved = f"Tell me about {target_x} regarding {prev_entity}."
                return True, resolved

        # Rule Case 1 (Hindi): "X का क्या हाल है?" / "X के बारे में?"
        # Example: Prev: "गोरखपुर में बाढ़ की क्या स्थिति है?" | Query: "राप्ती नदी का क्या हाल है?" -> "गोरखपुर में राप्ती नदी का क्या हाल है?"
        if any(p in query for p in self.FOLLOWUP_PHRASES_HI) and prev_entity:
            if prev_entity not in query:
                resolved = f"{prev_entity} में {query}"
                return True, resolved

        # Rule Case 2: English Pronouns ("its", "it", "there", "this", "that")
        # Example: Prev: "Tell me about Rapti river." | Query: "What is its current water level?" -> "What is Rapti river current water level?"
        for pronoun_pat in self.ENGLISH_PRONOUNS:
            if re.search(pronoun_pat, q_lower):
                if prev_entity:
                    resolved = re.sub(pronoun_pat, prev_entity, query, flags=re.IGNORECASE)
                    return True, resolved

        # Rule Case 3: Hindi Pronouns ("उसका", "उसकी", "वहाँ", "इसकी")
        for pronoun_pat in self.HINDI_PRONOUNS:
            if re.search(pronoun_pat, query):
                if prev_entity:
                    resolved = re.sub(pronoun_pat, f"{prev_entity} का", query)
                    return True, resolved

        # Rule Case 4: Short ellipsis/incomplete phrase (< 4 words)
        words = query.split()
        if len(words) <= 3 and prev_entity and prev_entity.lower() not in q_lower:
            if "flood" in p_user_lower or "बाढ़" in prev_user:
                resolved = f"{query} for {prev_entity} flood" if not re.search(r"[\u0900-\u097F]", query) else f"{prev_entity} में {query}"
                return True, resolved

        return False, query

    def _extract_main_subject(self, text: str) -> str:
        """
        Extracts the primary location/entity from query text.
        """
        cleaned = re.sub(r"^(tell me about|what is the|update on|what about|status of|info on|compare|explain|describe)\s+", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+(floods?|situation|status|update|details|report|\?|\.)$", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()
        return cleaned if cleaned else text

    def _contains_specific_subject(self, text: str) -> bool:
        """
        Returns True if text contains a specific entity or location name.
        """
        locations = ["bihar", "patna", "gorakhpur", "assam", "rapti", "kosi", "ganga", "बिहार", "पटना", "गोरखपुर", "असम", "राप्ती", "कोसी", "गंगा"]
        return any(loc in text.lower() for loc in locations)

    def _llm_resolution(self, query: str, history: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Uses LLM Adapter as fallback to rewrite ambiguous queries into standalone search queries.
        """
        history_snippet = []
        for turn in history[-2:]:
            history_snippet.append(f"User: {turn['user_query']}")
            history_snippet.append(f"Assistant: {turn['assistant_response'][:150]}...")
        
        hist_text = "\n".join(history_snippet)
        prompt = (
            "System: You are a query rewriting assistant. Given the conversation history, rewrite the user's latest follow-up question "
            "into a complete, self-contained standalone search query. Do NOT answer the question. If the question is an independent new topic, output it unchanged. Output ONLY the rewritten standalone query.\n\n"
            f"Conversation History:\n{hist_text}\n\n"
            f"Follow-up Question: {query}\n\n"
            "Standalone Query:"
        )

        try:
            llm_resp = self.llm_adapter.generate(prompt)
            rewritten = llm_resp.get("text", "").strip()
            rewritten = re.sub(r'^["\']|["\']$', '', rewritten).strip()
            if rewritten and rewritten.lower() != query.lower():
                return True, rewritten
        except Exception:
            pass

        return False, query

    def extract_research_context(self, query: str, history: Optional[List[Dict[str, Any]]] = None) -> Any:
        """
        Parses a research query into structured ResearchContext parameters:
        - disaster_types: list of detected disaster types (e.g. ['flood'], ['cyclone'])
        - geography: list of detected geographic regions (e.g. ['assam'], ['odisha'])
        - time_period: optional detected timeframe
        - research_topic: resolved topic summary string
        Handles follow-up entity and topic carry-over from conversation history.
        """
        from src.context_relevance_engine import ResearchContext
        
        # 1. Resolve query standalone text using prior turns if needed
        is_rewritten, resolved_query, _ = self.resolve_context(query, history or [])
        clean_text = resolved_query.lower()

        # 2. Detect Disaster Types
        disaster_types = []
        if any(w in clean_text for w in ["flood", "floods", "flooding", "waterlogging", "inundation", "inundated", "deluge", "baadh", "बाढ़", "जलभराव", "जलमग्न"]):
            disaster_types.append("flood")
        if any(w in clean_text for w in ["cyclone", "cyclones", "storm", "cyclonic", "storm surge", "तूफान", "चक्रवात"]):
            disaster_types.append("cyclone")
        if any(w in clean_text for w in ["landslide", "landslides", "mudslide", "debris flow", "rockfall", "भूस्खलन"]):
            disaster_types.append("landslide")
        if any(w in clean_text for w in ["drought", "droughts", "dry spell", "crop failure", "water scarcity", "सूखा", "अकाल"]):
            disaster_types.append("drought")
        if any(w in clean_text for w in ["cloudburst", "glof", "glacial lake"]):
            if "flood" not in disaster_types:
                disaster_types.append("flood")

        # 3. Detect Geography
        geography = []
        geo_map = {
            "assam": ["assam", "guwahati", "brahmaputra", "barpeta", "silchar", "dibrugarh", "jorhat", "असम", "गुवाहाटी"],
            "bihar": ["bihar", "patna", "kosi", "gandak", "darbhanga", "danapur", "chhapra", "saran", "bhagalpur", "बिहार", "पटना", "कोसी"],
            "odisha": ["odisha", "orissa", "bhubaneswar", "puri", "cuttack", "balasore", "mahanadi", "ओडिशा", "भुवनेश्वर"],
            "gorakhpur": ["gorakhpur", "rapti", "campierganj", "chauri chaura", "गोरखपुर", "राप्ती"],
            "mumbai": ["mumbai", "bombay", "maharashtra", "मुंबई", "महाराष्ट्र"],
            "sikkim": ["sikkim", "namchi", "gangtok", "सिक्किम", "गंगटोक"],
            "punjab": ["punjab", "पंजाब"],
            "kerala": ["kerala", "केरल"]
        }

        for canon_geo, terms in geo_map.items():
            if any(t in clean_text for t in terms):
                geography.append(canon_geo)

        # 4. Fallback from History if follow-up missing explicit entities
        if history:
            prev_turn = history[-1]
            prev_ctx = prev_turn.get("research_context")
            if isinstance(prev_ctx, dict):
                if not disaster_types and prev_ctx.get("disaster_types"):
                    disaster_types = list(prev_ctx["disaster_types"])
                if not geography and prev_ctx.get("geography"):
                    geography = list(prev_ctx["geography"])

        return ResearchContext(
            disaster_types=disaster_types,
            geography=geography,
            research_topic=resolved_query
        )
