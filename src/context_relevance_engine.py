import os
import re
import json
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

try:
    from src.embedding_providers import BaseEmbeddingProvider, SentenceTransformersProvider
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False

logger = logging.getLogger("ContextRelevanceEngine")

@dataclass
class ResearchContext:
    """
    Encapsulates research parameters for disaster intelligence filtering.
    """
    disaster_types: List[str] = field(default_factory=lambda: ["flood", "heavy rainfall", "inundation", "monsoon", "river overflow", "बाढ़"])
    geography: List[str] = field(default_factory=lambda: ["bihar", "assam", "patna", "mumbai", "india", "बिहार", "असम", "गंगा"])
    time_period: Optional[Any] = None
    source_types: List[str] = field(default_factory=lambda: ["News", "Official Report", "Research", "Blogs"])
    research_topic: str = "Disaster management, flood monitoring, heavy rainfall impact, river inundation, and emergency relief operations in India."
    custom_keywords: List[str] = field(default_factory=list)

    def to_embedding_text(self) -> str:
        d_str = ", ".join(self.disaster_types)
        g_str = ", ".join(self.geography)
        s_str = ", ".join(self.source_types)
        c_str = ", ".join(self.custom_keywords) if self.custom_keywords else ""
        return f"{self.research_topic} Disaster types: {d_str}. Geography: {g_str}. Sources: {s_str}. Keywords: {c_str}".strip()


class ContextRelevanceEngine:
    """
    VARTA Modular Context Relevance Engine:
    - Evaluates dataset/document records against Research Context using:
      1. Data Quality Checks (empty, malformed, gibberish, metadata completeness)
      2. Metadata & Context Signals
      3. Keyword & Phrase Signals (English & Hindi Devanagari + metaphor disambiguation)
      4. Dense Semantic Similarity matching
    - Produces normalized relevance score (0.0 to 1.0) and machine-readable reason code.
    - Classifies record into KEEP, REVIEW, or EXCLUDE.
    - Preserves all original document metadata and citation fields.
    - Missing URLs decrease metadata quality slightly but NEVER cause automatic content exclusion.
    """

    def __init__(self, config_path: Optional[str] = None, embedding_provider: Optional[Any] = None):
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if not config_path:
            config_path = os.path.join(self.project_root, "config", "context_relevance_config.json")
        
        self.config_path = os.path.abspath(config_path)
        self.config = self._load_config()

        # Extract weights & thresholds
        self.weights = self.config.get("weights", {"semantic_similarity": 0.50, "keyword_signals": 0.30, "metadata_signals": 0.20})
        self.thresholds = self.config.get("thresholds", {"keep_threshold": 0.60, "exclude_threshold": 0.35, "min_quality_for_keep": 0.50})
        self.quality_config = self.config.get("quality_checks", {"min_content_length": 15, "max_non_printable_ratio": 0.20, "missing_url_penalty": 0.10, "min_quality_score": 0.30})
        self.keywords = self.config.get("keywords", {})
        self.metaphor_penalty = self.config.get("metaphor_penalty", 0.40)

        # Initialize embedding provider if available
        self.embedding_provider = embedding_provider
        if self.embedding_provider is None and EMBEDDINGS_AVAILABLE:
            try:
                self.embedding_provider = SentenceTransformersProvider()
            except Exception as e:
                logger.warning(f"Could not load SentenceTransformersProvider: {e}")
                self.embedding_provider = None

        # Cached context embeddings
        self._cached_context_vector: Optional[np.ndarray] = None
        self._cached_context_text: Optional[str] = None

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "weights": {"semantic_similarity": 0.50, "keyword_signals": 0.30, "metadata_signals": 0.20},
            "thresholds": {"keep_threshold": 0.66, "exclude_threshold": 0.35, "min_quality_for_keep": 0.50},
            "quality_checks": {"min_content_length": 15, "max_non_printable_ratio": 0.20, "missing_url_penalty": 0.10, "min_quality_score": 0.30},
            "keywords": {"disaster_terms": ["flood", "inundation", "heavy rainfall", "monsoon", "river overflow", "बाढ़"], "geography_terms": ["bihar", "assam", "patna", "mumbai", "india"], "metaphor_terms": ["flood of sales", "flood of offers"]},
            "metaphor_penalty": 0.40
        }

    def _get_context_vector(self, context: ResearchContext) -> Optional[np.ndarray]:
        if not self.embedding_provider:
            return None
        
        ctx_text = context.to_embedding_text()
        if self._cached_context_text == ctx_text and self._cached_context_vector is not None:
            return self._cached_context_vector

        try:
            vec = self.embedding_provider.embed_query(ctx_text)
            self._cached_context_text = ctx_text
            self._cached_context_vector = vec
            return vec
        except Exception as e:
            logger.warning(f"Error embedding context: {e}")
            return None

    def evaluate_quality(self, record: Dict[str, Any]) -> Tuple[float, List[str]]:
        """
        Evaluates data quality: content emptiness, malformed text, gibberish ratio, length, missing URL.
        Note: Missing URL only reduces metadata quality score by penalty (e.g. 0.1), NOT invalidating content.
        """
        flags = []
        quality_score = 1.0

        # Extract text content
        title = str(record.get("title") or "").strip()
        content = str(record.get("text_content") or record.get("content") or "").strip()
        combined_text = f"{title} {content}".strip()

        # 1. Empty Content Check
        if not combined_text or len(combined_text) < self.quality_config.get("min_content_length", 15):
            flags.append("EMPTY_MALFORMED")
            return 0.0, flags

        # 2. Gibberish / Non-printable ratio
        non_printable_cnt = sum(1 for c in combined_text if not c.isprintable() and c not in ("\n", "\r", "\t"))
        ratio = non_printable_cnt / len(combined_text)
        if ratio > self.quality_config.get("max_non_printable_ratio", 0.20):
            flags.append("GIBBERISH_MALFORMED")
            quality_score -= 0.60

        # 3. Duplicate check flag
        if record.get("is_duplicate"):
            flags.append("DUPLICATE")
            quality_score -= 0.50

        # 4. Missing URL check (Metadata Quality signal only)
        raw_url = record.get("source_url") or record.get("url") or record.get("post_id") or ""
        has_valid_url = bool(raw_url and (str(raw_url).startswith("http://") or str(raw_url).startswith("https://")))

        if not has_valid_url:
            flags.append("MISSING_URL")
            quality_score -= self.quality_config.get("missing_url_penalty", 0.10)

        quality_score = max(0.0, min(1.0, round(quality_score, 4)))
        return quality_score, flags

    def evaluate_keywords(self, record: Dict[str, Any], context: ResearchContext) -> Tuple[float, bool, List[str]]:
        """
        Evaluates keyword & phrase signals in title and text.
        Includes contextual metaphor detection (e.g. 'flood of sales', 'iPhone launch').
        Geography keyword gating: Standalone geography terms do NOT contribute to keyword_score
        unless at least one disaster or custom context term is also present.
        """
        title = str(record.get("title") or "").strip().lower()
        content = str(record.get("text_content") or record.get("content") or "").strip().lower()
        full_text = f"{title} {content}"

        disaster_terms = set([t.lower() for t in self.keywords.get("disaster_terms", []) + context.disaster_types])
        geography_terms = set([t.lower() for t in self.keywords.get("geography_terms", []) + context.geography])
        custom_terms = set([t.lower() for t in context.custom_keywords])

        hit_disaster = [term for term in disaster_terms if term in full_text]
        hit_geography = [term for term in geography_terms if term in full_text]
        hit_custom = [term for term in custom_terms if term in full_text]

        # Geography keyword gating rule:
        # Standalone geography terms do NOT contribute to keyword_score unless at least one disaster or custom context term is present.
        if hit_disaster or hit_custom:
            hit_terms = hit_disaster + hit_geography + hit_custom
        else:
            hit_terms = []

        hit_count = len(hit_terms)

        # Base keyword score calculation
        if hit_count == 0:
            keyword_score = 0.0
        elif hit_count == 1:
            keyword_score = 0.50
        elif hit_count == 2:
            keyword_score = 0.75
        else:
            keyword_score = 1.0

        # Title bonus (only if valid hit_terms present)
        if hit_terms:
            title_hits = [term for term in hit_terms if term in title]
            if title_hits:
                keyword_score = min(1.0, keyword_score + 0.15)

        # Metaphor / Out-of-Domain Disambiguation Check
        metaphor_terms = set([t.lower() for t in self.keywords.get("metaphor_terms", [])])
        metaphor_detected = any(m in full_text for m in metaphor_terms)
        
        # Additional heuristic: "flood" present alongside commercial/tech terms without disaster terms
        commercial_terms = {"sales", "discount", "iphone", "market", "offers", "product", "movie", "box office"}
        if "flood" in full_text and any(c in full_text for c in commercial_terms) and not any(d in full_text for d in (disaster_terms - {"flood"})):
            metaphor_detected = True

        if metaphor_detected:
            keyword_score = max(0.0, keyword_score - self.metaphor_penalty)

        return round(keyword_score, 4), metaphor_detected, hit_terms

    def evaluate_metadata(self, record: Dict[str, Any], context: ResearchContext) -> float:
        """
        Evaluates metadata alignment (source type, category taxonomy, geography).
        Detects out-of-domain categories (e.g. Sports, Entertainment) to penalize score.
        """
        category = str(record.get("category_taxonomy") or "").strip().lower()
        title = str(record.get("title") or "").strip().lower()

        out_of_domain_terms = {"sports", "cricket", "football", "basketball", "tennis", "movie", "box office", "fashion", "gadget", "entertainment"}
        is_out_of_domain = any(ood in category or ood in title for ood in out_of_domain_terms)

        if is_out_of_domain:
            return 0.0

        # Neutral default metadata baseline (0.20) when disaster category is missing or non-disaster
        score = 0.20

        # Preserve stronger metadata score when reliable disaster-specific taxonomy actually exists
        has_disaster_category = category and any(dt.lower() in category for dt in context.disaster_types)
        if has_disaster_category:
            score += 0.60

        source_type = str(record.get("source_type") or "").strip().lower()
        if source_type and any(st.lower() in source_type for st in context.source_types):
            score += 0.10

        return max(0.0, min(1.0, round(score, 4)))

    def evaluate_semantic_similarity(self, record: Dict[str, Any], context: ResearchContext) -> float:
        """
        Computes dense semantic vector similarity between document payload and research context.
        """
        if not self.embedding_provider:
            # Fallback to keyword signal if embeddings provider not available
            kw_score, _, _ = self.evaluate_keywords(record, context)
            return kw_score

        ctx_vec = self._get_context_vector(context)
        if ctx_vec is None:
            kw_score, _, _ = self.evaluate_keywords(record, context)
            return kw_score

        title = str(record.get("title") or "").strip()
        content = str(record.get("text_content") or record.get("content") or "").strip()
        doc_text = f"{title}\n{content[:500]}".strip()

        try:
            doc_vec = self.embedding_provider.embed_query(doc_text)
            ctx_flat = np.array(ctx_vec, dtype=np.float32).flatten()
            doc_flat = np.array(doc_vec, dtype=np.float32).flatten()
            
            # Cosine similarity between normalized vectors
            norm_ctx = ctx_flat / (np.linalg.norm(ctx_flat) + 1e-10)
            norm_doc = doc_flat / (np.linalg.norm(doc_flat) + 1e-10)
            similarity = float(np.dot(norm_ctx, norm_doc))
            
            # Map similarity score [-1, 1] to [0, 1]
            similarity_norm = max(0.0, min(1.0, (similarity + 1.0) / 2.0))
            return round(similarity_norm, 4)
        except Exception as e:
            logger.warning(f"Error computing semantic similarity: {e}")
            kw_score, _, _ = self.evaluate_keywords(record, context)
            return kw_score

    def evaluate_record(
        self,
        record: Dict[str, Any],
        context: Optional[ResearchContext] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: Evaluates a dataset record and produces normalized context relevance score,
        data quality score, decision classification (KEEP, REVIEW, EXCLUDE), machine-readable reason,
        while preserving all original metadata and citation fields.
        """
        if context is None:
            context = ResearchContext()

        # 1. Quality Evaluation
        quality_score, quality_flags = self.evaluate_quality(record)

        # 2. Keyword & Metaphor Evaluation
        keyword_score, metaphor_detected, hit_terms = self.evaluate_keywords(record, context)

        # 3. Metadata Signal Evaluation
        metadata_score = self.evaluate_metadata(record, context)

        # 4. Semantic Similarity Evaluation
        semantic_score = self.evaluate_semantic_similarity(record, context)

        disaster_terms = set([t.lower() for t in self.keywords.get("disaster_terms", []) + context.disaster_types])
        has_disaster_keyword = any(term in disaster_terms for term in hit_terms)

        # If data quality is 0 (empty/malformed), immediately classify as EXCLUDE
        if quality_score == 0.0:
            relevance_score = 0.0
            decision = "EXCLUDE"
            reason = "EXCLUDE_EMPTY_MALFORMED"
        else:
            w_sem = self.weights.get("semantic_similarity", 0.50)
            w_key = self.weights.get("keyword_signals", 0.30)
            w_meta = self.weights.get("metadata_signals", 0.20)

            # If metadata score is 0.0 due to explicit out-of-domain category & no disaster keywords present
            if metadata_score == 0.0 and not has_disaster_keyword:
                effective_kw = 0.0
                raw_relevance = (w_sem * semantic_score * 0.35) # Heavy penalty for out-of-domain non-disaster documents
            else:
                effective_kw = keyword_score
                raw_relevance = (w_sem * semantic_score) + (w_key * effective_kw) + (w_meta * metadata_score)

            relevance_score = max(0.0, min(1.0, round(raw_relevance, 4)))

            # Decision Logic
            keep_thresh = self.thresholds.get("keep_threshold", 0.60)
            exclude_thresh = self.thresholds.get("exclude_threshold", 0.35)
            min_quality_keep = self.thresholds.get("min_quality_for_keep", 0.50)

            primary_flood_terms = {"flood", "floods", "flooded", "flooding", "baadh", "बाढ़"}
            has_primary_flood_term = any(term in primary_flood_terms for term in hit_terms)

            if metaphor_detected and semantic_score < 0.45:
                decision = "REVIEW" if relevance_score >= exclude_thresh else "EXCLUDE"
                reason = "REVIEW_KEYWORD_AMBIGUOUS_METAPHOR" if decision == "REVIEW" else "EXCLUDE_OUT_OF_DOMAIN_METAPHOR"
            elif relevance_score >= keep_thresh and quality_score >= min_quality_keep:
                decision = "KEEP"
                if "MISSING_URL" in quality_flags:
                    reason = "KEEP_MISSING_URL_HIGH_CONTENT_RELEVANCE"
                elif not has_primary_flood_term:
                    reason = "KEEP_SEMANTIC_MATCH_NO_EXPLICIT_KEYWORD"
                else:
                    reason = "KEEP_HIGH_SEMANTIC_MATCH"
            elif relevance_score < exclude_thresh or quality_score < self.quality_config.get("min_quality_score", 0.30):
                decision = "EXCLUDE"
                reason = "EXCLUDE_LOW_RELEVANCE" if relevance_score < exclude_thresh else "EXCLUDE_POOR_DATA_QUALITY"
            else:
                decision = "REVIEW"
                reason = "REVIEW_BORDERLINE_RELEVANCE"

        # Construct result dictionary PRESERVING ALL ORIGINAL FIELDS
        evaluated_record = dict(record) # Deep copy of record fields
        evaluated_record["context_relevance_score"] = relevance_score
        evaluated_record["data_quality_score"] = quality_score
        evaluated_record["relevance_decision"] = decision
        evaluated_record["relevance_reason"] = reason
        evaluated_record["evaluation_details"] = {
            "semantic_score": semantic_score,
            "keyword_score": keyword_score,
            "metadata_score": metadata_score,
            "metaphor_detected": metaphor_detected,
            "hit_terms": hit_terms,
            "quality_flags": quality_flags
        }

        return evaluated_record

    def evaluate_batch(
        self,
        records: List[Dict[str, Any]],
        context: Optional[ResearchContext] = None,
        batch_size: int = 32
    ) -> List[Dict[str, Any]]:
        """
        Optimized batch evaluation of dataset records.
        Generates dense semantic embeddings in vector batches (batch_size=32/64)
        and computes matrix dot product similarity in a single vectorized NumPy operation.
        """
        if not records:
            return []

        if context is None:
            context = ResearchContext()

        # Precompute context embedding once per session
        ctx_vec = self._get_context_vector(context)

        # Build payload texts for all records
        doc_texts = []
        for r in records:
            title = str(r.get("title") or "").strip()
            content = str(r.get("text_content") or r.get("content") or "").strip()
            doc_texts.append(f"{title}\n{content[:500]}".strip())

        # Batch semantic similarity computation
        semantic_scores = []
        if self.embedding_provider and ctx_vec is not None:
            ctx_flat = np.array(ctx_vec, dtype=np.float32).flatten()
            norm_ctx = ctx_flat / (np.linalg.norm(ctx_flat) + 1e-10)

            try:
                # Use batch encoding across all texts
                doc_embeddings = self.embedding_provider.encode(doc_texts)
                norm_docs = doc_embeddings / (np.linalg.norm(doc_embeddings, axis=1, keepdims=True) + 1e-10)
                sims = np.dot(norm_docs, norm_ctx)
                sims_norm = np.clip((sims + 1.0) / 2.0, 0.0, 1.0)
                semantic_scores = [round(float(s), 4) for s in sims_norm]
            except Exception as e:
                logger.warning(f"Error in batch semantic embedding: {e}")
                semantic_scores = [None] * len(records)
        else:
            semantic_scores = [None] * len(records)

        # Evaluate rules and construct evaluated records
        evaluated_records = []
        for idx, record in enumerate(records):
            sem_score = semantic_scores[idx]
            if sem_score is None:
                sem_score = self.evaluate_semantic_similarity(record, context)

            quality_score, quality_flags = self.evaluate_quality(record)
            keyword_score, metaphor_detected, hit_terms = self.evaluate_keywords(record, context)
            metadata_score = self.evaluate_metadata(record, context)

            disaster_terms = set([t.lower() for t in self.keywords.get("disaster_terms", []) + context.disaster_types])
            has_disaster_keyword = any(term in disaster_terms for term in hit_terms)

            if quality_score == 0.0:
                relevance_score = 0.0
                decision = "EXCLUDE"
                reason = "EXCLUDE_EMPTY_MALFORMED"
            else:
                w_sem = self.weights.get("semantic_similarity", 0.50)
                w_key = self.weights.get("keyword_signals", 0.30)
                w_meta = self.weights.get("metadata_signals", 0.20)

                if metadata_score == 0.0 and not has_disaster_keyword:
                    effective_kw = 0.0
                    raw_relevance = (w_sem * sem_score * 0.35)
                else:
                    effective_kw = keyword_score
                    raw_relevance = (w_sem * sem_score) + (w_key * effective_kw) + (w_meta * metadata_score)

                relevance_score = max(0.0, min(1.0, round(raw_relevance, 4)))

                keep_thresh = self.thresholds.get("keep_threshold", 0.66)
                exclude_thresh = self.thresholds.get("exclude_threshold", 0.35)
                min_quality_keep = self.thresholds.get("min_quality_for_keep", 0.50)

                primary_flood_terms = {"flood", "floods", "flooded", "flooding", "baadh", "बाढ़"}
                has_primary_flood_term = any(term in primary_flood_terms for term in hit_terms)

                if metaphor_detected and sem_score < 0.45:
                    decision = "REVIEW" if relevance_score >= exclude_thresh else "EXCLUDE"
                    reason = "REVIEW_KEYWORD_AMBIGUOUS_METAPHOR" if decision == "REVIEW" else "EXCLUDE_OUT_OF_DOMAIN_METAPHOR"
                elif relevance_score >= keep_thresh and quality_score >= min_quality_keep:
                    decision = "KEEP"
                    if "MISSING_URL" in quality_flags:
                        reason = "KEEP_MISSING_URL_HIGH_CONTENT_RELEVANCE"
                    elif not has_primary_flood_term:
                        reason = "KEEP_SEMANTIC_MATCH_NO_EXPLICIT_KEYWORD"
                    else:
                        reason = "KEEP_HIGH_SEMANTIC_MATCH"
                elif relevance_score < exclude_thresh or quality_score < self.quality_config.get("min_quality_score", 0.30):
                    decision = "EXCLUDE"
                    reason = "EXCLUDE_LOW_RELEVANCE" if relevance_score < exclude_thresh else "EXCLUDE_POOR_DATA_QUALITY"
                else:
                    decision = "REVIEW"
                    reason = "REVIEW_BORDERLINE_RELEVANCE"

            evaluated_record = dict(record)
            evaluated_record["context_relevance_score"] = relevance_score
            evaluated_record["data_quality_score"] = quality_score
            evaluated_record["relevance_decision"] = decision
            evaluated_record["relevance_reason"] = reason
            evaluated_record["evaluation_details"] = {
                "semantic_score": sem_score,
                "keyword_score": keyword_score,
                "metadata_score": metadata_score,
                "metaphor_detected": metaphor_detected,
                "hit_terms": hit_terms,
                "quality_flags": quality_flags
            }
            evaluated_records.append(evaluated_record)

        return evaluated_records

    def filter_dataset(
        self,
        records: List[Dict[str, Any]],
        context: Optional[ResearchContext] = None,
        allowed_decisions: Tuple[str, ...] = ("KEEP", "REVIEW")
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Evaluates a batch/list of dataset records and returns the filtered records
        matching allowed_decisions along with processing statistics.
        Uses optimized batch matrix evaluation.
        """
        if context is None:
            context = ResearchContext()

        evaluated_records = self.evaluate_batch(records, context)
        filtered_records = []
        decision_counts = {"KEEP": 0, "REVIEW": 0, "EXCLUDE": 0}
        reason_counts = {}

        for eval_rec in evaluated_records:
            dec = eval_rec["relevance_decision"]
            rsn = eval_rec["relevance_reason"]
            decision_counts[dec] = decision_counts.get(dec, 0) + 1
            reason_counts[rsn] = reason_counts.get(rsn, 0) + 1

            if dec in allowed_decisions:
                filtered_records.append(eval_rec)

        stats = {
            "total_inspected": len(records),
            "total_passed": len(filtered_records),
            "total_excluded": len(records) - len(filtered_records),
            "decision_counts": decision_counts,
            "reason_counts": reason_counts,
            "pass_rate_pct": round((len(filtered_records) / len(records)) * 100, 2) if records else 0.0
        }

        return filtered_records, stats
