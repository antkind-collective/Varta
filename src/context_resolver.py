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

    ENGLISH_PRONOUNS = {r"\bits\b", r"\bit\b", r"\bthis\b", r"\bthat\b", r"\bthey\b", r"\bthem\b"}
    HINDI_PRONOUNS = {r"\bउसका\b", r"\bउसकी\b", r"\bउसके\b", r"\bवह\b", r"\bवहाँ\b", r"\bइसकी\b", r"\bइसके\b", r"\bइन्हें\b"}

    FOLLOWUP_PREAMBLES_EN = (r"^what about\b", r"^how about\b", r"^and\s+(?:what|how|why|which|where)\b")
    FOLLOWUP_PHRASES_HI = ("का क्या हाल है", "क्या हाल है", "के बारे में क्या", "और बताएँ")

    STANDALONE_OPENERS = (r"^tell me about\b", r"^explain\b", r"^describe\b", r"^details on\b", r"^information on\b", r"^what is\b", r"^compare\b", r"^are there\b", r"^is there\b", r"^were there\b", r"^was there\b", r"^how do\b", r"^why do\b", r"^what are\b")

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
        words = query.split()

        # 1. Check if query starts with explicit standalone opener like "Are there any...", "Tell me about..."
        starts_with_standalone_opener = any(re.search(op, q_lower) for op in self.STANDALONE_OPENERS)
        if starts_with_standalone_opener and len(words) >= 5:
            # Check that it doesn't contain an explicit unresolved deictic pronoun like "in that city"
            if not re.search(r"\b(in that (?:city|state|area|region|district)|there|its)\b", q_lower):
                return True

        # 2. Check for deictic/referential pronouns in English (excluding existential 'there' and relative 'that')
        has_pronoun = False
        if re.search(r"\b(its|it)\b", q_lower) and not re.search(r"\b(it is|it was|it's)\b", q_lower):
            has_pronoun = True
        elif re.search(r"\b(in that (?:state|city|area|region|district)|about that|about this)\b", q_lower):
            has_pronoun = True
        elif re.search(r"\b(what about (?:them|those|these|it))\b", q_lower):
            has_pronoun = True
        elif any(re.search(p, query) for p in self.HINDI_PRONOUNS):
            has_pronoun = True

        if has_pronoun:
            return False

        # 3. Check if query contains explicit follow-up preambles
        has_followup_preamble = any(re.search(p, q_lower) for p in self.FOLLOWUP_PREAMBLES_EN)
        if has_followup_preamble:
            return False

        has_followup_phrase_hi = any(p in query for p in self.FOLLOWUP_PHRASES_HI)
        if has_followup_phrase_hi:
            return False

        # 4. Check for short detail/impact follow-up questions lacking location (e.g. "which districts are affected?")
        is_detail_followup = bool(re.search(r"^(which districts|worst affected|affected areas|casualties|deaths|damage|losses|relief|rescue|causes?|reasons?|why)\b", q_lower))
        if is_detail_followup and not self._contains_specific_subject(query):
            return False

        # 5. Check if query is a short fragment (< 4 words) missing a main subject -> NOT standalone
        if len(words) <= 3 and not self._contains_specific_subject(query):
            return False

        # 6. Default: if query has >= 5 words and no follow-up markers, treat as standalone
        if len(words) >= 5:
            return True

        return False

    def _try_rule_based_resolution(self, query: str, prev_user: str, prev_asst: str) -> Tuple[bool, str]:
        """
        Applies deterministic pattern matching and entity carry-over rules for genuine follow-ups.
        """
        q_lower = query.lower()
        p_user_lower = prev_user.lower()

        prev_entity = self._extract_main_subject(prev_user)
        if not prev_entity or len(prev_entity) > 35 or len(prev_entity.split()) > 4:
            # If previous turn has no clear named entity, avoid corrupting subsequent queries
            return False, query

        # Rule Case 0: Clarification / Scope specification (e.g. "im talking about disasters" / "about floods")
        if re.search(r"^(i'?m\s+talking\s+about|talking\s+about|about|specifically)\s+(disasters?|floods?|landslides?|cyclones?)", q_lower):
            disaster_match = re.search(r"(disasters?|floods?|landslides?|cyclones?)", q_lower)
            d_word = disaster_match.group(1) if disaster_match else "disasters"
            resolved = f"{d_word.capitalize()} in {prev_entity}"
            return True, resolved

        # Rule Case 1: "What about X?" / "How about X?"
        match_about = re.match(r"^(what about|how about)\s+(.+)$", query, re.IGNORECASE)
        if match_about:
            target_x = match_about.group(2).strip(" ?.")
            if target_x.lower() not in prev_entity.lower():
                if "flood" in p_user_lower or "बाढ़" in prev_user:
                    resolved = f"What is the flood situation in {target_x}, {prev_entity}?"
                else:
                    resolved = f"Tell me about {target_x} regarding {prev_entity}."
                return True, resolved

        # Rule Case 1 (Hindi): "X का क्या हाल है?" / "X के बारे में?"
        if any(p in query for p in self.FOLLOWUP_PHRASES_HI):
            if prev_entity not in query:
                resolved = f"{prev_entity} में {query}"
                return True, resolved

        # Rule Case 2: Explicit locative deictic references ("in that area", "there", "its")
        if re.search(r"\b(in that (?:city|state|area|region|district)|there)\b", q_lower):
            resolved = re.sub(r"\b(in that (?:city|state|area|region|district)|there)\b", f"in {prev_entity}", query, flags=re.IGNORECASE)
            return True, resolved

        if re.search(r"^what is its\b", q_lower):
            resolved = re.sub(r"^what is its\b", f"what is {prev_entity}'s", query, flags=re.IGNORECASE)
            return True, resolved

        # Rule Case 3: Hindi Pronouns ("उसका", "उसकी", "वहाँ", "इसकी")
        for pronoun_pat in self.HINDI_PRONOUNS:
            if re.search(pronoun_pat, query):
                resolved = re.sub(pronoun_pat, f"{prev_entity} का", query)
                return True, resolved

        # Rule Case 4: Detail / Impact / Causes / Attribution follow-up query missing location
        if not self._contains_specific_subject(query):
            if re.search(r"^(which districts|worst affected|affected areas|casualties|deaths|damage|losses|relief|rescue|causes?|reasons?|why)\b", q_lower):
                resolved = f"{query.rstrip('?.')} in {prev_entity}?"
                return True, resolved

        # Rule Case 5: Short ellipsis/incomplete phrase (< 4 words)
        words = query.split()
        if len(words) <= 3 and prev_entity.lower() not in q_lower:
            if "flood" in p_user_lower or "बाढ़" in prev_user:
                resolved = f"{query} for {prev_entity} flood" if not re.search(r"[\u0900-\u097F]", query) else f"{prev_entity} में {query}"
                return True, resolved

        return False, query

    def _extract_main_subject(self, text: str) -> str:
        """
        Extracts the primary location/entity from query text.
        Guarantees that full sentences or complex analytical clauses are never returned as entities.
        """
        text_lower = text.lower()
        geo_keywords = {
            "assam": "Assam", "bihar": "Bihar", "odisha": "Odisha", "patna": "Patna",
            "gorakhpur": "Gorakhpur", "guwahati": "Guwahati", "sivasagar": "Sivasagar",
            "kosi": "Kosi River", "rapti": "Rapti River", "brahmaputra": "Brahmaputra River",
            "mumbai": "Mumbai", "chennai": "Chennai", "bengaluru": "Bengaluru", "bangalore": "Bengaluru",
            "delhi": "Delhi", "kerala": "Kerala", "wayanad": "Wayanad", "sikkim": "Sikkim",
            "himachal": "Himachal Pradesh", "uttarakhand": "Uttarakhand", "gujarat": "Gujarat",
            "असम": "असम", "बिहार": "बिहार", "पटना": "पटना", "गोरखपुर": "गोरखपुर", "ओडिशा": "ओडिशा"
        }
        for kw, canonical in geo_keywords.items():
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                return canonical

        cleaned = re.sub(r"^(tell me about|what is the|update on|what about|status of|info on|compare|explain|describe)\s+", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+(floods?|situation|status|update|details|report|\?|\.)$", "", cleaned, flags=re.IGNORECASE).strip()
        
        # If cleaned phrase is too long or contains verbs/clauses, reject as a subject
        if len(cleaned) > 30 or len(cleaned.split()) > 4 or any(w in cleaned.lower().split() for w in ["is", "are", "were", "was", "how", "why", "describe", "experienced", "mentioned", "talk"]):
            return ""

        return cleaned if cleaned else ""

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
            u_q = turn.get("user_query") or turn.get("query") or ""
            a_r = turn.get("assistant_response") or turn.get("response") or turn.get("answer") or ""
            history_snippet.append(f"User: {u_q}")
            history_snippet.append(f"Assistant: {a_r[:150]}...")
        
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

        # 3. Detect Geography & Specific Sub-regions/Cities
        geography = []
        specific_location = ""
        geo_map = {
            "assam": ["assam", "guwahati", "brahmaputra", "barpeta", "silchar", "dibrugarh", "jorhat", "dhemaji", "dhubri", "असम", "गुवाहाटी"],
            "bihar": ["bihar", "patna", "kosi", "gandak", "darbhanga", "danapur", "chhapra", "saran", "bhagalpur", "बिहार", "पटना", "कोसी"],
            "odisha": ["odisha", "orissa", "bhubaneswar", "puri", "cuttack", "balasore", "mahanadi", "ओडिशा", "भुवनेश्वर"],
            "gorakhpur": ["gorakhpur", "rapti", "campierganj", "chauri chaura", "गोरखपुर", "राप्ती"],
            "mumbai": ["mumbai", "bombay", "maharashtra", "thane", "pune", "मुंबई", "महाराष्ट्र"],
            "chennai": ["chennai", "madras", "tamil nadu", "tamilnadu", "adyar", "cooum", "चेन्नई", "तमिलनाडु"],
            "delhi": ["delhi", "yamuna", "ncr", "noida", "ghaziabad", "gurugram", "दिल्ली", "यमुना"],
            "gujarat": ["gujarat", "ahmedabad", "surat", "vadodara", "rajkot", "गुजरात", "अहमदाबाद"],
            "himachal": ["himachal", "shimla", "manali", "kullu", "mandi", "beas", "हिमाचल", "मनाली"],
            "uttarakhand": ["uttarakhand", "kedarnath", "rishikesh", "haridwar", "dehradun", "chamoli", "उत्तराखंड", "ऋषिकेश"],
            "kerala": ["kerala", "wayanad", "kozhikode", "idukki", "munnar", "केरल"],
            "sikkim": ["sikkim", "namchi", "gangtok", "सिक्किम", "गंगटोक"],
            "punjab": ["punjab", "ludhiana", "amritsar", "sutlej", "पंजाब"],
            "karnataka": ["karnataka", "bengaluru", "bangalore", "mysuru", "कर्नाटक", "बेंगलुरु"],
            "andhra": ["andhra", "vijayawada", "visakhapatnam", "godavari", "krishna", "आंध्र"],
            "bengal": ["bengal", "kolkata", "hooghly", "teesta", "पश्चिम बंगाल", "कोलकाता"]
        }

        specific_city_terms = {
            "chennai": "Chennai", "चेन्नई": "Chennai", "madras": "Chennai", "tamil nadu": "Tamil Nadu",
            "guwahati": "Guwahati", "गुवाहाटी": "Guwahati",
            "patna": "Patna", "पटना": "Patna",
            "danapur": "Danapur", "darbhanga": "Darbhanga", "bhagalpur": "Bhagalpur", "chhapra": "Chhapra",
            "silchar": "Silchar", "dibrugarh": "Dibrugarh", "barpeta": "Barpeta", "jorhat": "Jorhat", "dhemaji": "Dhemaji",
            "mumbai": "Mumbai", "मुंबई": "Mumbai", "thane": "Thane", "pune": "Pune",
            "bhubaneswar": "Bhubaneswar", "भुवनेश्वर": "Bhubaneswar", "puri": "Puri", "cuttack": "Cuttack",
            "gorakhpur": "Gorakhpur", "गोरखपुर": "Gorakhpur",
            "delhi": "Delhi", "दिल्ली": "Delhi", "noida": "Noida",
            "ahmedabad": "Ahmedabad", "surat": "Surat", "gujarat": "Gujarat",
            "dehradun": "Dehradun", "rishikesh": "Rishikesh", "haridwar": "Haridwar",
            "shimla": "Shimla", "manali": "Manali", "kullu": "Kullu",
            "wayanad": "Wayanad", "kozhikode": "Kozhikode",
            "bengaluru": "Bengaluru", "bangalore": "Bengaluru",
            "kolkata": "Kolkata",
            "gangtok": "Gangtok", "गंगटोक": "Gangtok"
        }

        for term, formatted in specific_city_terms.items():
            if term in clean_text:
                specific_location = formatted
                break

        for canon_geo, terms in geo_map.items():
            if any(t in clean_text for t in terms):
                geography.append(canon_geo)

        # 4. Detect Disaster Domain vs Specific Disaster Types
        domain = "disaster"  # Default domain in VARTA
        is_generic_disaster = any(w in clean_text for w in ["disaster", "disasters", "calamity", "hazard", "catastrophe", "emergency", "आपदा", "विपदा"])
        if is_generic_disaster and not disaster_types:
            domain = "disaster"

        # 5. Detect Analytical Intent / Inquiry Dimensions (Layer 2)
        analytical_intent = []
        if any(w in clean_text for w in ["cause", "causes", "reason", "reasons", "driver", "drivers", "why", "contributing", "factors"]):
            analytical_intent.append("causes")
        if any(w in clean_text for w in ["god", "human", "humans", "nature", "climate change", "think", "thought", "believe", "belief", "beliefs", "attribute", "attribution", "blame", "perception", "perceptions"]):
            analytical_intent.append("attribution_beliefs")
        if any(w in clean_text for w in ["human activity", "human activities", "human action", "human actions", "encroachment", "deforestation", "construction", "anthropogenic"]):
            if "human_activities" not in analytical_intent:
                analytical_intent.append("human_activities")
        if any(w in clean_text for w in ["district", "districts", "worst affected", "affected areas", "affected"]):
            analytical_intent.append("affected_regions")
        if any(w in clean_text for w in ["damage", "submerged", "inundated", "casualties", "deaths", "toll", "impact", "impacts"]):
            analytical_intent.append("impacts")
        if any(w in clean_text for w in ["relief", "rescue", "evacuation", "camp", "ndrf", "sdrf", "assistance", "response"]):
            analytical_intent.append("relief_response")
        if any(w in clean_text for w in ["trend", "trends", "historical", "over time", "past years"]):
            analytical_intent.append("trends")

        # 6. Fallback and Entity Carry-over from Conversation History
        if history:
            for past_turn in reversed(history):
                prev_ctx = past_turn.get("research_context")
                prev_u_q = str(past_turn.get("user_query") or past_turn.get("query") or "").lower()

                # Carry over geography if not explicit in current turn
                if not geography:
                    if isinstance(prev_ctx, dict) and prev_ctx.get("geography"):
                        geography = list(prev_ctx["geography"])
                    elif isinstance(prev_ctx, ResearchContext) and prev_ctx.geography:
                        geography = list(prev_ctx.geography)
                    else:
                        for canon_geo, terms in geo_map.items():
                            if any(t in prev_u_q for t in terms):
                                geography.append(canon_geo)
                                break

                # Carry over specific location
                if not specific_location:
                    if isinstance(prev_ctx, dict) and prev_ctx.get("specific_location"):
                        specific_location = str(prev_ctx["specific_location"])
                    elif isinstance(prev_ctx, ResearchContext) and prev_ctx.specific_location:
                        specific_location = str(prev_ctx.specific_location)
                    else:
                        for term, formatted in specific_city_terms.items():
                            if term in prev_u_q:
                                specific_location = formatted
                                break

                # Carry over disaster types if not explicit in current turn
                if not disaster_types and not is_generic_disaster:
                    if isinstance(prev_ctx, dict) and prev_ctx.get("disaster_types"):
                        disaster_types = list(prev_ctx["disaster_types"])
                    elif isinstance(prev_ctx, ResearchContext) and prev_ctx.disaster_types:
                        disaster_types = list(prev_ctx.disaster_types)

                if geography:
                    break

        return ResearchContext(
            domain=domain,
            disaster_types=disaster_types,
            geography=geography,
            specific_location=specific_location,
            analytical_intent=analytical_intent,
            research_topic=resolved_query
        )

