import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
import numpy as np
from src.data_cleaner import DataCleaner
from src.duplicate_handler import DuplicateHandler
from src.text_normalizer import TextNormalizer
from src.context_relevance_engine import ContextRelevanceEngine, ResearchContext
from src.context_resolver import ContextResolver
from src.embedding_providers import BaseEmbeddingProvider

class MockEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        
    def _vectorize(self, text: str) -> np.ndarray:
        t_low = text.lower()
        vec = np.zeros(self.dimension, dtype=np.float32)
        
        is_commercial = any(w in t_low for w in ["offers", "sales", "discount", "iphone", "price cuts", "retail"])
        if is_commercial:
            vec[350:384] = 1.0
        else:
            if any(w in t_low for w in ["flood", "floods", "flooding", "inundat", "submerg", "deluge", "marooned", "waterlogging", "बाढ़", "जलमग्न"]):
                vec[0:50] = 1.0
            if any(w in t_low for w in ["cyclone", "cyclones", "storm surge", "gale", "तूफान", "चक्रवात"]):
                vec[50:100] = 1.0
            if any(w in t_low for w in ["landslide", "mudslide", "debris flow", "भूस्खलन"]):
                vec[100:150] = 1.0
            if any(w in t_low for w in ["drought", "dry spell", "water scarcity", "सूखा"]):
                vec[150:200] = 1.0

            if any(w in t_low for w in ["assam", "guwahati", "brahmaputra", "barpeta", "dhemaji", "असम"]):
                vec[200:250] = 1.0
            if any(w in t_low for w in ["bihar", "patna", "kosi", "danapur", "बिहार", "पटना"]):
                vec[250:300] = 1.0
            if any(w in t_low for w in ["odisha", "puri", "bhubaneswar", "gopalpur", "ओडिशा"]):
                vec[300:350] = 1.0

        norm = np.linalg.norm(vec)
        if norm > 0:
            return vec / norm
        else:
            np.random.seed(abs(hash(text)) % (2**31))
            v = np.random.randn(self.dimension).astype(np.float32)
            return v / (np.linalg.norm(v) + 1e-10)

    def encode(self, texts: list, batch_size: int = 256) -> np.ndarray:
        return np.array([self._vectorize(t) for t in texts], dtype=np.float32)
        
    def embed_query(self, text: str) -> np.ndarray:
        return np.expand_dims(self._vectorize(text), axis=0)
        
    def get_dimension(self) -> int:
        return self.dimension
        
    def get_model_name(self) -> str:
        return "mock-embedding-provider"

class TestDynamicContextRelevance(unittest.TestCase):
    """
    Validation Test Suite for VARTA Realignment:
    1. Permanent Data-Quality Cleaning (Clean Master Dataset construction).
    2. Dynamic Context-Specific Relevance Filtering (Floods in Assam vs. Cyclones in Odisha).
    3. Multi-turn Research Context Resolution.
    """

    def setUp(self):
        self.mock_emb = MockEmbeddingProvider(dimension=384)
        self.engine = ContextRelevanceEngine(embedding_provider=self.mock_emb)
        self.resolver = ContextResolver()

    # -------------------------------------------------------------
    # SUITE 1: Permanent Data-Quality Cleaning Tests
    # -------------------------------------------------------------
    def test_permanent_cleaning_duplicate_detection(self):
        """Validates that exact duplicates and content hash collisions are identified for permanent drop."""
        records = [
            {"post_id": "P001", "title": "Assam Flood Alert", "text_content": "Brahmaputra river is flowing above danger mark."},
            {"post_id": "P001", "title": "Assam Flood Alert", "text_content": "Brahmaputra river is flowing above danger mark."}, # Duplicate ID
            {"post_id": "P002", "title": "Assam Flood Alert", "text_content": "Brahmaputra river is flowing above danger mark."}, # Content hash duplicate
            {"post_id": "P003", "title": "Odisha Cyclone Warning", "text_content": "Super cyclone approaching Puri coast."}
        ]
        dup_handler = DuplicateHandler(id_column="post_id", payload_columns=["title", "text_content"])
        import pandas as pd
        df = pd.DataFrame(records)
        df_clean, report = dup_handler.deduplicate(df)
        
        self.assertEqual(len(df_clean), 2, "DuplicateHandler should drop exact ID and content hash duplicates")
        self.assertEqual(set(df_clean["post_id"].tolist()), {"P001", "P003"})

    def test_permanent_cleaning_empty_and_malformed(self):
        """Validates that empty payloads and gibberish are flagged with 0 quality score."""
        cleaner = DataCleaner({"identifier_column": "post_id", "core_payload_columns": ["title", "text_content"]})
        
        empty_rec = {"post_id": "P_EMPTY", "title": "", "text_content": "   "}
        score_empty, flags_empty = self.engine.evaluate_quality(empty_rec)
        self.assertEqual(score_empty, 0.0)
        self.assertIn("EMPTY_MALFORMED", flags_empty)

        gibberish_rec = {"post_id": "P_GIBBER", "title": "\x00\x01\x02\x03\x04\x05\x06\x07", "text_content": "\x00\x08\x0b\x0c\x0e\x0f\x10\x11\x12\x13"}
        score_gib, flags_gib = self.engine.evaluate_quality(gibberish_rec)
        self.assertIn("GIBBERISH_MALFORMED", flags_gib)

    def test_permanent_cleaning_missing_url_retained(self):
        """Validates that a valid document with missing URL is retained with high content quality."""
        valid_no_url = {
            "post_id": "P_NO_URL",
            "title": "Severe flooding in Guwahati after cloudburst",
            "text_content": "Heavy monsoon rains have submerged vast parts of Guwahati city with SDRF deployed for relief.",
            "category_taxonomy": "Natural Disasters - Floods",
            "source_type": "News",
            "source_url": ""
        }
        score, flags = self.engine.evaluate_quality(valid_no_url)
        self.assertGreaterEqual(score, 0.85, "Missing URL should only slightly penalize metadata, not invalidate valid content")
        self.assertIn("MISSING_URL", flags)
        
        # Test evaluation against Assam flood context
        ctx = ResearchContext(disaster_types=["flood"], geography=["assam"], research_topic="Floods in Assam")
        eval_res = self.engine.evaluate_record(valid_no_url, context=ctx)
        self.assertEqual(eval_res["relevance_decision"], "KEEP")
        self.assertIn("KEEP_MISSING_URL", eval_res["relevance_reason"])

    # -------------------------------------------------------------
    # SUITE 2: Dynamic Context-Specific Relevance Filtering
    # -------------------------------------------------------------
    def test_dynamic_context_floods_in_assam(self):
        """Validates scoring for 'Floods in Assam' context."""
        context_assam_flood = ResearchContext(
            disaster_types=["flood"],
            geography=["assam"],
            research_topic="Floods in Assam"
        )

        assam_flood_doc = {
            "post_id": "DOC_ASSAM_01",
            "title": "Brahmaputra river breaches embankment in Barpeta Assam",
            "text_content": "Over 200 villages inundated as heavy monsoon flood waters submerge homes and crops in Barpeta, Assam. NDRF teams active.",
            "category_taxonomy": "Natural Disasters - Floods",
            "source_type": "News"
        }
        bihar_flood_doc = {
            "post_id": "DOC_BIHAR_01",
            "title": "Kosi river rises above danger level in Patna Bihar",
            "text_content": "Inundation reported across Danapur and Patna as Kosi river water level surges after heavy rains in Bihar.",
            "category_taxonomy": "Natural Disasters - Floods",
            "source_type": "News"
        }
        odisha_cyclone_doc = {
            "post_id": "DOC_ODISHA_01",
            "title": "Super Cyclone strikes Puri and coastal Odisha",
            "text_content": "Destructive gale winds and storm surges hit Gopalpur and Puri coast in Odisha. Thousands evacuated to cyclone shelters.",
            "category_taxonomy": "Natural Disasters - Cyclones",
            "source_type": "News"
        }
        metaphor_doc = {
            "post_id": "DOC_METAPHOR_01",
            "title": "E-commerce festive season brings flood of offers and sales discounts",
            "text_content": "Customers in Guwahati witness a flood of offers, massive price cuts, and iPhone launch discounts across major retail markets.",
            "category_taxonomy": "Business & Commercial",
            "source_type": "News"
        }
        semantic_no_keyword_doc = {
            "post_id": "DOC_SEMANTIC_01",
            "title": "Villagers marooned and cut off by raging river waters in Dhemaji",
            "text_content": "In Dhemaji district, hundreds of families are trapped on rooftops as overflowing river currents submerge roads and bridges.",
            "category_taxonomy": "Disaster Relief",
            "source_type": "Official Report"
        }

        # 1. Assam Flood Doc -> KEEP
        res_assam = self.engine.evaluate_record(assam_flood_doc, context=context_assam_flood)
        self.assertEqual(res_assam["relevance_decision"], "KEEP", "Assam flood article must be KEPT for Assam flood context")
        self.assertGreaterEqual(res_assam["context_relevance_score"], 0.60)

        # 2. Bihar Flood Doc -> EXCLUDE (Geographic Mismatch)
        res_bihar = self.engine.evaluate_record(bihar_flood_doc, context=context_assam_flood)
        self.assertEqual(res_bihar["relevance_decision"], "EXCLUDE", "Bihar flood article must be EXCLUDED from Assam flood context")
        self.assertLessEqual(res_bihar["context_relevance_score"], 0.35)
        self.assertEqual(res_bihar["relevance_reason"], "EXCLUDE_GEOGRAPHIC_MISMATCH")

        # 3. Odisha Cyclone Doc -> EXCLUDE (Disaster and Geography Mismatch)
        res_odisha = self.engine.evaluate_record(odisha_cyclone_doc, context=context_assam_flood)
        self.assertEqual(res_odisha["relevance_decision"], "EXCLUDE", "Odisha cyclone must be EXCLUDED from Assam flood context")
        self.assertLessEqual(res_odisha["context_relevance_score"], 0.35)

        # 4. Metaphor Doc -> EXCLUDE (Commercial Metaphor False Positive)
        res_metaphor = self.engine.evaluate_record(metaphor_doc, context=context_assam_flood)
        self.assertEqual(res_metaphor["relevance_decision"], "EXCLUDE", "Commercial metaphor 'flood of offers' must be EXCLUDED")
        self.assertLessEqual(res_metaphor["context_relevance_score"], 0.35)
        self.assertEqual(res_metaphor["relevance_reason"], "EXCLUDE_OUT_OF_DOMAIN_METAPHOR")

        # 5. Semantic No Keyword Doc -> KEEP (Preserved via semantic + geography signals)
        res_semantic = self.engine.evaluate_record(semantic_no_keyword_doc, context=context_assam_flood)
        self.assertEqual(res_semantic["relevance_decision"], "KEEP", "Assam marooned article without keyword 'flood' must be discoverable via semantic matching")
        self.assertGreaterEqual(res_semantic["context_relevance_score"], 0.60)

    def test_dynamic_reversibility_cyclones_in_odisha(self):
        """
        Validates that switching context to 'Cyclones in Odisha' reverses relevance
        without deleting documents from the underlying dataset.
        """
        context_odisha_cyclone = ResearchContext(
            disaster_types=["cyclone"],
            geography=["odisha"],
            research_topic="Cyclones in Odisha"
        )

        assam_flood_doc = {
            "post_id": "DOC_ASSAM_01",
            "title": "Brahmaputra river breaches embankment in Barpeta Assam",
            "text_content": "Over 200 villages inundated as heavy monsoon flood waters submerge homes and crops in Barpeta, Assam. NDRF teams active.",
            "category_taxonomy": "Natural Disasters - Floods",
            "source_type": "News"
        }
        odisha_cyclone_doc = {
            "post_id": "DOC_ODISHA_01",
            "title": "Super Cyclone strikes Puri and coastal Odisha",
            "text_content": "Destructive gale winds and storm surges hit Gopalpur and Puri coast in Odisha. Thousands evacuated to cyclone shelters.",
            "category_taxonomy": "Natural Disasters - Cyclones",
            "source_type": "News"
        }

        # In Odisha Cyclone Context:
        res_odisha_new = self.engine.evaluate_record(odisha_cyclone_doc, context=context_odisha_cyclone)
        res_assam_new = self.engine.evaluate_record(assam_flood_doc, context=context_odisha_cyclone)

        self.assertEqual(res_odisha_new["relevance_decision"], "KEEP", "Odisha cyclone article must be KEPT for Odisha cyclone context")
        self.assertGreaterEqual(res_odisha_new["context_relevance_score"], 0.60)

        self.assertEqual(res_assam_new["relevance_decision"], "EXCLUDE", "Assam flood article must be EXCLUDED from Odisha cyclone context")
        self.assertLessEqual(res_assam_new["context_relevance_score"], 0.35)

    def test_context_resolver_parameter_extraction(self):
        """Validates query extraction into structured disaster and geography parameters."""
        ctx1 = self.resolver.extract_research_context("Tell me about floods in Assam and Brahmaputra river status.")
        self.assertIn("flood", ctx1.disaster_types)
        self.assertIn("assam", ctx1.geography)

        ctx2 = self.resolver.extract_research_context("What is the cyclone update for coastal Odisha?")
        self.assertIn("cyclone", ctx2.disaster_types)
        self.assertIn("odisha", ctx2.geography)

        # Multi-turn follow-up test:
        history = [
            {"user_query": "What is the flood situation in Bihar?", "assistant_response": "Severe flooding reported across Bihar."}
        ]
        ctx3 = self.resolver.extract_research_context("What about Patna?", history=history)
        self.assertIn("flood", ctx3.disaster_types, "Follow-up should inherit flood disaster type from prior turn")
        self.assertIn("bihar", ctx3.geography)

if __name__ == "__main__":
    unittest.main()
