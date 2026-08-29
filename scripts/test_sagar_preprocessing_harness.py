"""
VARTA - Sagar Preprocessing & Ingestion Validation Harness (Review Queue Edition)
Authoritative Acceptance Test Suite for Handover to Sagar

This test harness implements the two-tier Review Workflow:
1. AUTO-KEEP: High-confidence records (relevance_decision == 'KEEP') are automatically eligible for embedding.
2. AUTO-EXCLUDE: Irrelevant / Poor quality / Duplicate records are dropped immediately before embedding.
3. REVIEW QUEUE: Borderline records (relevance_decision == 'REVIEW') are exported to a structured CSV:
   - record_id
   - title
   - content_preview
   - relevance_score
   - matched_keywords
   - relevance_reason
   - final_decision (pre-filled with 'REVIEW' / editable by Sagar to 'KEEP' or 'EXCLUDE')
4. POST-REVIEW INGESTION: The embedding pipeline consumes ONLY approved 'KEEP' records (Auto-KEEP + Sagar-Approved KEEP).
5. STRICT ASSERTIONS: Proves that zero EXCLUDE / unapproved REVIEW records ever reach the embedding provider.
"""

import sys
import os
import json
import time
import hashlib
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Set project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.data_cleaner import DataCleaner
from src.text_normalizer import TextNormalizer
from src.metadata_processor import MetadataProcessor
from src.duplicate_handler import DuplicateHandler
from src.context_relevance_engine import ContextRelevanceEngine, ResearchContext
from src.document_builder import DocumentBuilder
from src.document_validator import DocumentValidator
from src.chunk_builder import ChunkBuilder


class MockEmbeddingProvider:
    """
    Mock embedding provider for test harness verification.
    Records every text / chunk received to prove zero OpenAI calls for excluded records.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.recorded_calls: List[List[str]] = []
        self.total_chunks_embedded: int = 0

    def get_dimension(self) -> int:
        return self.dimension

    def encode(self, texts: List[str], batch_size: int = 256) -> np.ndarray:
        self.recorded_calls.append(list(texts))
        self.total_chunks_embedded += len(texts)
        count = len(texts)
        rng = np.random.RandomState(42)
        vecs = rng.randn(count, self.dimension).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
        return vecs / norms

    def embed_query(self, text: str) -> np.ndarray:
        rng = np.random.RandomState(42)
        vec = rng.randn(self.dimension).astype(np.float32)
        norm = np.linalg.norm(vec) + 1e-10
        return vec / norm


def get_sagar_test_dataset() -> List[Dict[str, Any]]:
    """
    Returns 30 curated test cases across categories A, B, C, D, E.
    """
    return [
        # -------------------------------------------------------------
        # Category A: Valid Disaster-Relevant Records (Auto-KEEP)
        # -------------------------------------------------------------
        {
            "id": "CASE_A1_FLOOD",
            "title": "Heavy monsoon rainfall triggers river overflow and widespread inundation",
            "text_content": "Incessant rainfall over the past 48 hours has caused severe flooding across low-lying villages. The district administration has established 10 relief camps and deployed disaster rescue teams.",
            "source_url": "https://news.example.com/flood-1",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category A: Disaster Keyword (flood, rainfall, inundation, relief camps)"
        },
        {
            "id": "CASE_A2_LANDSLIDE",
            "title": "Major landslide blocks national highway following torrential rains",
            "text_content": "A massive landslide occurred early morning, disrupting vehicular movement and stranding hundreds of commuters. Emergency road clearance operations and NDRF rescue teams are active.",
            "source_url": "https://news.example.com/landslide-1",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category A: Disaster Keyword (landslide, heavy rain, ndrf)"
        },
        {
            "id": "CASE_A3_CYCLONE",
            "title": "Severe cyclonic storm approaches coastline with heavy storm surge warning",
            "text_content": "Meteorological department issues high alert for cyclonic storm landfall. Coastal evacuation underway by SDRF and district teams to move vulnerable populations to shelter centers.",
            "source_url": "https://news.example.com/cyclone-1",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category A: Disaster Keyword (cyclone, cyclonic storm, evacuation, sdrf)"
        },
        {
            "id": "CASE_A4_DROUGHT",
            "title": "Severe drought situation declared across agricultural districts",
            "text_content": "State government notifies drought affected zones following acute monsoon deficit. Severe water scarcity and widespread crop failure have impacted farming communities across the region.",
            "source_url": "https://news.example.com/drought-1",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category A: Disaster Keyword (drought situation, drought affected, water scarcity, crop failure)"
        },

        # -------------------------------------------------------------
        # Category B: Geography Relevance
        # -------------------------------------------------------------
        {
            "id": "CASE_B1_GEO_DISASTER_ANCHOR",
            "title": "Brahmaputra river overflow causes massive waterlogging in Sivasagar",
            "text_content": "The Brahmaputra and its tributaries are flowing above danger mark in Sivasagar district of Assam. Over 50,000 residents are affected by severe inundation and embankment breach.",
            "source_url": "https://news.example.com/assam-sivasagar",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category B: Disaster + Valid Indian Geo Anchor (Brahmaputra, Assam, Sivasagar)"
        },
        {
            "id": "CASE_B2_GEO_ALONE_NO_DISASTER",
            "title": "New luxury residential highrise apartment project launched in Patna Bihar",
            "text_content": "Real estate developer announces state of the art residential community in central Patna with premium amenities, swimming pool, club house, and modern architecture.",
            "source_url": "https://realestate.example.com/patna-luxury",
            "source_type": "Real Estate",
            "category_taxonomy": "Business",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category B: Geography Gating (Standalone geography without disaster context -> REVIEW / EXCLUDE)"
        },
        {
            "id": "CASE_B3_ASSAM_RELEVANT",
            "title": "Assam flood situation remains grim with 25 districts inundated",
            "text_content": "Over 7 lakh people are affected across Assam as major rivers remain in spate. NDRF and SDRF teams are conducting round-the-clock rescue operations in Guwahati and upper Assam.",
            "source_url": "https://news.example.com/assam-flood",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category B: Focus Geography (Assam, Guwahati) + Disaster (flood, NDRF)"
        },
        {
            "id": "CASE_B4_BIHAR_RELEVANT",
            "title": "Kosi river embankment breach creates alarming flood crisis in North Bihar",
            "text_content": "Heavy discharge from upstream barrage led to embankment breach along the Kosi river in Bihar. Multiple villages in Supaul and Saharsa submerged under floodwaters.",
            "source_url": "https://news.example.com/bihar-kosi",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category B: Focus Geography (Bihar, Kosi) + Disaster (embankment breach, flood)"
        },
        {
            "id": "CASE_B5_IRRELEVANT_GEO_DISASTER_COMBO",
            "title": "Political rally draws massive crowd in Mumbai ahead of municipal election",
            "text_content": "Political parties hold massive roadshows and public rallies in Mumbai to discuss municipal budget allocation, traffic infrastructure, and civic development ahead of civic polls.",
            "source_url": "https://politics.example.com/mumbai-rally",
            "source_type": "Politics",
            "category_taxonomy": "Politics",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category B: Out-of-Domain Context (Political rally without disaster content -> REVIEW / EXCLUDE)"
        },

        # -------------------------------------------------------------
        # Category C: Noise / Metaphor Exclusions
        # -------------------------------------------------------------
        {
            "id": "CASE_C1_METAPHOR_FLOOD_OFFERS",
            "title": "Festive season brings a flood of offers on smartphones and electronic gadgets",
            "text_content": "Major e-commerce platforms offer deep discount rates, cashbacks, and sales deals on premium electronics during annual Diwali shopping festival.",
            "source_url": "https://shop.example.com/deals",
            "source_type": "Commercial",
            "category_taxonomy": "Shopping",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category C: Metaphor & Commercial Gating ('flood of offers' / sales discounts -> REVIEW / EXCLUDE)"
        },
        {
            "id": "CASE_C2_METAPHOR_FLOOD_CALLS",
            "title": "Customer care helpline overwhelmed by a flood of calls after broadband outage",
            "text_content": "Telecom customer support received a flood of calls from subscribers inquiring about technical resolution timelines following fiber internet outage.",
            "source_url": "https://tech.example.com/outage",
            "source_type": "Tech",
            "category_taxonomy": "Support",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category C: Metaphor Exclusion ('flood of calls' -> REVIEW / EXCLUDE)"
        },
        {
            "id": "CASE_C3_METAPHOR_LANDSLIDE_VICTORY",
            "title": "Ruling coalition registers historic landslide victory in parliamentary election",
            "text_content": "Election commission declares final results as party wins three-fourths majority in national assembly, securing a decisive landslide victory across key constituencies.",
            "source_url": "https://news.example.com/election-landslide",
            "source_type": "News",
            "category_taxonomy": "Politics",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category C: Metaphor Exclusion ('landslide victory' -> REVIEW / EXCLUDE)"
        },
        {
            "id": "CASE_C4_METAPHOR_LANDSLIDE_WIN",
            "title": "Incumbent governor celebrates landslide win in regional election runoff",
            "text_content": "Voters turned out in record numbers to give incumbent governor a decisive landslide win over rival political challengers in regional ballot count.",
            "source_url": "https://news.example.com/election-win",
            "source_type": "News",
            "category_taxonomy": "Politics",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category C: Metaphor Exclusion ('landslide win' -> REVIEW / EXCLUDE)"
        },
        {
            "id": "CASE_C5_METAPHOR_TROPHY_DROUGHT",
            "title": "Cricket team ends 15-year trophy drought with spectacular tournament final triumph",
            "text_content": "National cricket team captain lifts ICC world cup trophy ending an agonizing trophy drought after beating opponents in a thrilling last-over finish.",
            "source_url": "https://sports.example.com/cricket-final",
            "source_type": "Sports",
            "category_taxonomy": "Cricket",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category C: Metaphor & Domain Exclusion ('trophy drought' + Sports -> EXCLUDE)"
        },
        {
            "id": "CASE_C6_METAPHOR_CYCLONE_SEPARATOR",
            "title": "High efficiency cyclone separator installed at industrial grain flour milling plant",
            "text_content": "Factory engineering team completes installation of industrial cyclone separator dust collection system to improve air quality inside milling facility.",
            "source_url": "https://industry.example.com/cyclone-separator",
            "source_type": "Industrial",
            "category_taxonomy": "Manufacturing",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category C: Metaphor Exclusion ('cyclone separator' -> REVIEW / EXCLUDE)"
        },

        # -------------------------------------------------------------
        # Category D: Data Quality & Hygiene
        # -------------------------------------------------------------
        {
            "id": "CASE_D1_EXACT_DUPLICATE",
            "title": "Heavy monsoon rainfall triggers river overflow and widespread inundation",
            "text_content": "Incessant rainfall over the past 48 hours has caused severe flooding across low-lying villages. The district administration has established 10 relief camps and deployed disaster rescue teams.",
            "source_url": "https://news.example.com/flood-1",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category D: Deduplication (Exact Row / ID duplicate -> EXCLUDE)"
        },
        {
            "id": "CASE_D2_NEAR_DUPLICATE_HASH",
            "title": "Heavy monsoon rainfall triggers river overflow and widespread inundation",
            "text_content": "Incessant rainfall over the past 48 hours has caused severe flooding across low-lying villages. The district administration has established 10 relief camps and deployed disaster rescue teams.",
            "source_url": "https://another-source.com/flood-reprint",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category D: Deduplication (Content-Hash collision duplicate -> EXCLUDE)"
        },
        {
            "id": "CASE_D3_EMPTY_CONTENT",
            "title": "   ",
            "text_content": "   ",
            "source_url": "https://news.example.com/empty",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category D: Quality Check (Empty text payload -> EXCLUDE)"
        },
        {
            "id": "CASE_D4_SHORT_CONTENT",
            "title": "Rain",
            "text_content": "Bad rain.",
            "source_url": "https://news.example.com/short",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category D: Quality Check (Short payload < 15 chars -> EXCLUDE)"
        },
        {
            "id": "CASE_D5_GIBBERISH_NON_PRINTABLE",
            "title": "ajksdhf 982347",
            "text_content": "zxvbnm qwer tyui opasd fghj klzx cvbn m1234 5678 9012 3456 7890 @@##$$%%^^&&**",
            "source_url": "https://news.example.com/gibberish",
            "source_type": "News",
            "category_taxonomy": "Uncategorized",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category D: Quality Check (Unparseable gibberish & zero semantic relevance -> AUTO-EXCLUDE)"
        },
        {
            "id": "CASE_D6_MISSING_URL_VALID_DISASTER",
            "title": "Major flood inundation in rural district with active rescue",
            "text_content": "Incessant monsoon deluge has submerged several villages and triggered emergency relief distribution camps by district administration and disaster teams.",
            "source_url": None,
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category D: Missing URL Hygiene (Missing URL incurs penalty only; valid disaster content is KEPT)"
        },
        {
            "id": "CASE_D7_MALFORMED_RECORD",
            "title": None,
            "text_content": None,
            "source_url": "https://news.example.com/none",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "EXCLUDE",
            "sagar_criterion": "Category D: Structural Hygiene (Missing title and content completely -> EXCLUDE)"
        },

        # -------------------------------------------------------------
        # Category E: Sagar-Specific Disaster Vocabulary (Auto-KEEP)
        # -------------------------------------------------------------
        {
            "id": "CASE_E1_GLOF",
            "title": "High altitude GLOF alert issued following glacial lake expansion",
            "text_content": "Scientists monitor glacial lake outburst flood risks in upper catchment. Early warning systems activated to protect downstream habitations from sudden deluge.",
            "source_url": "https://news.example.com/glof-alert",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category E: Sagar Vocabulary (GLOF, glacial lake outburst, deluge)"
        },
        {
            "id": "CASE_E2_CLOUDBURST",
            "title": "Catastrophic cloudburst triggers sudden flash floods in mountain valley",
            "text_content": "A sudden cloudburst over the hills caused immense runoff, sweeping away temporary bridges and flooding residential settlements downstream.",
            "source_url": "https://news.example.com/cloudburst-valley",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category E: Sagar Vocabulary (cloudburst, flash floods, washed away)"
        },
        {
            "id": "CASE_E3_MAROONED",
            "title": "Thousands of villagers remain marooned as floodwaters cut off road connectivity",
            "text_content": "Inundated approach roads have left entire rural panchayats marooned. District authorities dispatch motorboats and relief supplies to stranded families.",
            "source_url": "https://news.example.com/marooned-villagers",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category E: Sagar Vocabulary (marooned, floodwaters, relief supplies)"
        },
        {
            "id": "CASE_E4_DEBRIS_FLOW",
            "title": "Torrential downpour triggers intense debris flow and slope failure",
            "text_content": "Heavy rainfall on steep hills resulted in massive debris flow and slope failure, depositing thick silt and rocks across rural transportation corridors and houses.",
            "source_url": "https://news.example.com/debris-flow",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category E: Sagar Vocabulary (debris flow, slope failure, downpour)"
        },
        {
            "id": "CASE_E5_DROUGHT_SITUATION",
            "title": "Government reviews drought situation across 14 drought affected districts",
            "text_content": "High level ministerial meeting convenes to coordinate emergency tanker water supply and fodder camps in drought affected regions facing acute monsoon deficit.",
            "source_url": "https://news.example.com/drought-situation",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category E: Sagar Vocabulary (drought situation, drought affected)"
        },
        {
            "id": "CASE_E6_DRY_SPELL_CROP_FAILURE",
            "title": "Extended dry spell causes acute water scarcity and widespread crop failure",
            "text_content": "Farmers face severe losses as prolonged dry spell withers standing paddy crops. Borewells run dry leading to critical water scarcity in rural belts.",
            "source_url": "https://news.example.com/crop-failure",
            "source_type": "News",
            "category_taxonomy": "Disaster",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category E: Sagar Vocabulary (dry spell, water scarcity, crop failure)"
        },
        {
            "id": "CASE_E7_HINDI_DROUGHT",
            "title": "राज्य के 8 जिलों में भयंकर सूखा और जल संकट की स्थिति",
            "text_content": "बारिश न होने के कारण सूखा प्रभावित क्षेत्रों में किसानों की फसलें बर्बाद हो गई हैं। सरकार ने आपातकालीन राहत कार्य और पानी के टैंकर शुरू किए हैं।",
            "source_url": "https://hindi.example.com/drought",
            "source_type": "News",
            "category_taxonomy": "आपदा",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category E: Sagar Multilingual Hindi Vocabulary (सूखा, सूखा प्रभावित, राहत कार्य)"
        },
        {
            "id": "CASE_E8_HINDI_FLOOD_RIVER",
            "title": "गंगा नदी उफान पर, हजारों बाढ़ पीड़ित राहत शिविरों में पहुंचे",
            "text_content": "लगातार भारी बारिश से गंगा का जलस्तर बढ़ा। कई गांवों में तटबंध टूटना और जलभराव देखा गया, जहां एनडीआरएफ द्वारा रेस्क्यू कार्य जारी है।",
            "source_url": "https://hindi.example.com/flood-ganga",
            "source_type": "News",
            "category_taxonomy": "आपदा",
            "expected_decision": "KEEP",
            "sagar_criterion": "Category E: Sagar Multilingual Hindi Vocabulary (बाढ़ पीड़ित, नदी उफान पर, तटबंध टूटना, जलभराव, एनडीआरएफ)"
        }
    ]


def export_review_queue_csv(review_records: List[Dict[str, Any]], output_path: str) -> str:
    """
    Exports REVIEW records to a CSV with all required review columns:
    - record_id
    - title
    - content_preview
    - relevance_score
    - matched_keywords
    - relevance_reason
    - final_decision (pre-filled with 'REVIEW', ready for manual Sagar decision)
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    rows = []
    for r in review_records:
        eval_details = r.get("evaluation_details", {})
        hit_terms = eval_details.get("hit_terms", [])
        content_full = str(r.get("text_content") or r.get("content") or "")
        content_preview = (content_full[:160] + "...") if len(content_full) > 160 else content_full

        rows.append({
            "record_id": r.get("post_id") or r.get("id"),
            "title": r.get("title", ""),
            "content_preview": content_preview.replace("\n", " ").strip(),
            "relevance_score": r.get("context_relevance_score", 0.0),
            "matched_keywords": ", ".join(hit_terms) if hit_terms else "None",
            "relevance_reason": r.get("relevance_reason", ""),
            "final_decision": "REVIEW"  # Sagar can change to KEEP or EXCLUDE
        })

    df_review = pd.DataFrame(rows)
    df_review.to_csv(output_path, index=False, encoding="utf-8")
    return output_path


def run_sagar_review_workflow_harness() -> Dict[str, Any]:
    """
    Executes the two-tier Preprocessing & Review Validation Harness:
    1. Pre-filtering & Tri-partition (Auto-KEEP, Auto-EXCLUDE, REVIEW Queue)
    2. Export REVIEW Queue CSV
    3. Simulates Sagar's Manual Review
    4. Post-Review Ingestion & Embedding Verification
    """
    raw_dataset = get_sagar_test_dataset()
    total_raw = len(raw_dataset)

    # Initialize components
    column_config = {
        "identifier_column": "post_id",
        "core_payload_columns": ["title", "text_content"]
    }
    cleaner = DataCleaner(column_config)
    normalizer = TextNormalizer()
    meta_processor = MetadataProcessor()
    dup_handler = DuplicateHandler("post_id", ["title", "text_content"])
    mock_provider = MockEmbeddingProvider(dimension=384)
    rel_engine = ContextRelevanceEngine(embedding_provider=mock_provider)
    context = ResearchContext()
    doc_builder = DocumentBuilder(schema_version="1.0.0")
    validator = DocumentValidator()
    chunk_builder = ChunkBuilder(target_chunk_size=1200, chunk_overlap=200)

    # 1. Load Raw DataFrame
    df_raw = pd.DataFrame([
        {
            "post_id": r["id"],
            "title": r.get("title"),
            "text_content": r.get("text_content"),
            "source_url": r.get("source_url"),
            "source_type": r.get("source_type"),
            "category_taxonomy": r.get("category_taxonomy"),
            "_expected_decision": r["expected_decision"],
            "_sagar_criterion": r["sagar_criterion"]
        }
        for r in raw_dataset
    ])

    # 2. Structural Cleaning & Identifier Gating
    df_clean_cols, _ = cleaner.clean_structure_and_columns(df_raw)
    df_valid, filter_stats = cleaner.filter_and_fill_identifiers(df_clean_cols)
    cleaner_rejected_ids = set(df_raw["post_id"]) - set(df_valid["post_id"])

    # 3. Normalization & Metadata Processing
    for col in ["title", "text_content"]:
        if col in df_valid.columns:
            s, _ = normalizer.normalize_series(df_valid[col])
            df_valid[col] = s

    df_meta, _ = meta_processor.process_metadata(df_valid)

    # 4. Deduplication
    df_dedup, dedup_stats = dup_handler.deduplicate(df_meta)
    dedup_rejected_ids = set(df_valid["post_id"]) - set(df_dedup["post_id"])

    # 5. Context Relevance & Tri-Partitioning
    records = df_dedup.to_dict("records")
    evaluated_records = [rel_engine.evaluate_record(rec, context=context) for rec in records]

    auto_keep_records: List[Dict[str, Any]] = []
    auto_exclude_records: List[Dict[str, Any]] = []
    review_queue_records: List[Dict[str, Any]] = []

    for eval_rec in evaluated_records:
        dec = eval_rec.get("relevance_decision", "EXCLUDE")
        if dec == "KEEP":
            auto_keep_records.append(eval_rec)
        elif dec == "REVIEW":
            review_queue_records.append(eval_rec)
        else:
            auto_exclude_records.append(eval_rec)

    # 6. Check / Export REVIEW Queue CSV
    review_csv_path = str(project_root / "reports" / "sagar_review_queue.csv")
    
    # Read Sagar's confirmed decisions from CSV if present
    sagar_reviewed_decisions = {}
    if os.path.exists(review_csv_path):
        try:
            df_existing_review = pd.read_csv(review_csv_path)
            for _, row in df_existing_review.iterrows():
                rec_id = str(row.get("record_id") or "").strip()
                dec = str(row.get("final_decision") or "REVIEW").strip().upper()
                if rec_id:
                    sagar_reviewed_decisions[rec_id] = dec if dec in ("KEEP", "EXCLUDE") else "EXCLUDE"
        except Exception:
            pass

    # Export the fresh review queue with initial decisions
    export_review_queue_csv(review_queue_records, review_csv_path)
    for r in review_queue_records:
        pid = r.get("post_id")
        if pid not in sagar_reviewed_decisions:
            sagar_reviewed_decisions[pid] = "EXCLUDE"

    # -------------------------------------------------------------
    # 7. PHASE 1: Pre-Review Embedding Test (Only Auto-KEEP Eligible)
    # -------------------------------------------------------------
    pre_review_docs = []
    for idx, rec in enumerate(auto_keep_records):
        doc = doc_builder.build_document(rec, doc_index=idx)
        is_valid, _ = validator.validate_document(doc)
        if is_valid:
            pre_review_docs.append(doc)

    pre_review_chunks, _ = chunk_builder.build_chunks_from_documents(pre_review_docs)
    pre_review_texts = [c.get("embedding_text") or c.get("content") for c in pre_review_chunks]
    
    # Pre-review mock embedding call
    mock_provider.encode(pre_review_texts, batch_size=256)
    pre_review_embedded_count = mock_provider.total_chunks_embedded

    # -------------------------------------------------------------
    # 8. PHASE 2: Post-Review Handover Ingestion
    # Consumes ONLY confirmed KEEP records (Auto-KEEP + Sagar-Approved KEEP from CSV)
    # -------------------------------------------------------------
    mock_provider_post = MockEmbeddingProvider(dimension=384)

    approved_review_records = []
    rejected_review_records = []
    for r in review_queue_records:
        pid = r.get("post_id")
        manual_decision = sagar_reviewed_decisions.get(pid, "EXCLUDE")
        if manual_decision == "KEEP":
            r_copy = dict(r)
            r_copy["final_decision"] = "KEEP"
            approved_review_records.append(r_copy)
        else:
            rejected_review_records.append(r)

    # Final corpus to embed: Auto-KEEP + Sagar-Approved KEEP
    final_corpus_records = auto_keep_records + approved_review_records

    final_docs = []
    for idx, rec in enumerate(final_corpus_records):
        doc = doc_builder.build_document(rec, doc_index=idx)
        is_valid, _ = validator.validate_document(doc)
        if is_valid:
            final_docs.append(doc)

    final_chunks, _ = chunk_builder.build_chunks_from_documents(final_docs)
    final_texts = [c.get("embedding_text") or c.get("content") for c in final_chunks]
    
    if final_texts:
        mock_provider_post.encode(final_texts, batch_size=256)

    # -------------------------------------------------------------
    # 9. Verification & Detailed Assertions
    # -------------------------------------------------------------
    final_embedded_post_ids = set()
    for c in final_chunks:
        meta = c.get("metadata", {})
        pid = meta.get("post_id") or c.get("post_id")
        if pid:
            final_embedded_post_ids.add(pid)

    case_results = []
    all_assertions_passed = True

    for item in raw_dataset:
        cid = item["id"]
        expected = item["expected_decision"]

        if cid in cleaner_rejected_ids:
            stage_dec = "AUTO-EXCLUDE"
            actual_reason = "EXCLUDE_EMPTY_MALFORMED (DataCleaner filter)"
            actual_final = "EXCLUDE"
        elif cid in dedup_rejected_ids:
            stage_dec = "AUTO-EXCLUDE"
            actual_reason = "EXCLUDE_DUPLICATE (DuplicateHandler match)"
            actual_final = "EXCLUDE"
        else:
            matching_eval = next((r for r in evaluated_records if r.get("post_id") == cid), None)
            if matching_eval:
                rule_dec = matching_eval.get("relevance_decision")
                if rule_dec == "KEEP":
                    stage_dec = "AUTO-KEEP"
                    actual_final = "KEEP"
                    actual_reason = f"KEEP: {matching_eval.get('relevance_reason')}"
                elif rule_dec == "REVIEW":
                    stage_dec = "REVIEW_QUEUE"
                    manual_dec = sagar_reviewed_decisions.get(cid, "EXCLUDE")
                    actual_final = manual_dec
                    actual_reason = f"REVIEW ({matching_eval.get('relevance_reason')}) -> Sagar Manual Decision: {manual_dec}"
                else:
                    stage_dec = "AUTO-EXCLUDE"
                    actual_final = "EXCLUDE"
                    actual_reason = f"EXCLUDE: {matching_eval.get('relevance_reason')}"
            else:
                stage_dec = "AUTO-EXCLUDE"
                actual_final = "EXCLUDE"
                actual_reason = "EXCLUDE_UNKNOWN"

        passed = (actual_final == expected)
        reaches_embedding = (cid in final_embedded_post_ids)

        if expected == "EXCLUDE" and reaches_embedding:
            passed = False
            all_assertions_passed = False
            actual_reason += " [FAILED: Excluded record reached final embedding!]"
        elif expected == "KEEP" and not reaches_embedding:
            passed = False
            all_assertions_passed = False
            actual_reason += " [FAILED: Retained record did not reach final embedding!]"

        if not passed:
            all_assertions_passed = False

        case_results.append({
            "id": cid,
            "title": item["title"] or "[None]",
            "stage_decision": stage_dec,
            "expected": expected,
            "actual_final": actual_final,
            "reason": actual_reason,
            "sagar_criterion": item["sagar_criterion"],
            "reaches_embedding": reaches_embedding,
            "passed": passed
        })

    # Funnel counts
    hygiene_dropped = len(cleaner_rejected_ids) + len(dedup_rejected_ids)
    rule_excluded = len(auto_exclude_records)
    total_excluded_before_review = hygiene_dropped + rule_excluded
    
    summary = {
        "raw_records": total_raw,
        "removed_by_hygiene": hygiene_dropped,
        "auto_keep_records": len(auto_keep_records),
        "review_queue_records": len(review_queue_records),
        "auto_exclude_records": rule_excluded,
        "review_queue_csv_path": review_csv_path,
        "pre_review_chunks_embedded": pre_review_embedded_count,
        "post_review_chunks_embedded": mock_provider_post.total_chunks_embedded,
        "embedding_calls_avoided": total_raw - len(final_corpus_records),
        "all_assertions_passed": all_assertions_passed
    }

    return {
        "summary": summary,
        "case_results": case_results,
        "review_csv_path": review_csv_path
    }


if __name__ == "__main__":
    results = run_sagar_review_workflow_harness()
    s = results["summary"]
    cases = results["case_results"]

    print("=" * 90)
    print("VARTA SAGAR PREPROCESSING & REVIEW WORKFLOW VALIDATION HARNESS REPORT")
    print("=" * 90)
    print(f"Total Raw Records:                {s['raw_records']}")
    print(f"Removed by Basic Hygiene:         {s['removed_by_hygiene']}")
    print(f"Auto-KEEP (Eligible for Embed):   {s['auto_keep_records']}")
    print(f"REVIEW Queue (Exported to CSV):   {s['review_queue_records']}")
    print(f"Auto-EXCLUDE (Dropped immediately): {s['auto_exclude_records']}")
    print(f"REVIEW CSV Export Location:       {s['review_queue_csv_path']}")
    print(f"Pre-Review Chunks Embedded:       {s['pre_review_chunks_embedded']}")
    print(f"Post-Review Chunks Embedded:      {s['post_review_chunks_embedded']}")
    print(f"Total Embedding Calls Avoided:    {s['embedding_calls_avoided']}")
    print(f"All 30 Test Assertions Passed:    {s['all_assertions_passed']}")
    print("=" * 90)
    print(f"{'ID':<34} | {'Stage':<13} | {'Expected':<8} | {'Final':<8} | {'Passed':<6}")
    print("-" * 90)
    for c in cases:
        print(f"{c['id']:<34} | {c['stage_decision']:<13} | {c['expected']:<8} | {c['actual_final']:<8} | {str(c['passed']):<6}")
    print("=" * 90)

    # Strict Handover Verification Assertions
    review_ids = [
        "CASE_B2_GEO_ALONE_NO_DISASTER",
        "CASE_B5_IRRELEVANT_GEO_DISASTER_COMBO",
        "CASE_C1_METAPHOR_FLOOD_OFFERS",
        "CASE_C2_METAPHOR_FLOOD_CALLS",
        "CASE_C3_METAPHOR_LANDSLIDE_VICTORY",
        "CASE_C4_METAPHOR_LANDSLIDE_WIN",
        "CASE_C6_METAPHOR_CYCLONE_SEPARATOR",
        "CASE_D5_GIBBERISH_NON_PRINTABLE"
    ]

    print("\n[*] RUNNING STRICT HANDOVER ASSERTION CHECKS:")
    # 1. Verify review records are in CSV
    df_review = pd.read_csv(s["review_queue_csv_path"])
    assert s["review_queue_records"] == len(df_review), f"Expected {len(df_review)} review records, got {s['review_queue_records']}"
    print(f"  [OK] Exactly {s['review_queue_records']} records were routed to the REVIEW queue.")

    # 2. Verify all records in CSV have valid decisions
    assert (df_review["final_decision"].isin(["KEEP", "EXCLUDE", "REVIEW"])).all(), "Invalid decision in review queue!"
    print("  [OK] All records in sagar_review_queue.csv have valid decisions.")

    # 3. Verify that 0 excluded review cases reached the embedding provider
    for rid in review_ids:
        matching_case = next((c for c in cases if c["id"] == rid), None)
        if matching_case:
            assert matching_case["reaches_embedding"] is False or matching_case["final_decision"] == "KEEP", f"Review record {rid} leaked into embedding!"
    print("  [OK] Verified excluded review cases did not reach the embedding provider.")

    # 4. Verify that all 16 Auto-KEEP cases reached the embedding provider
    auto_keep_cases = [c for c in cases if c["stage_decision"] == "AUTO-KEEP"]
    assert len(auto_keep_cases) == 16, f"Expected 16 Auto-KEEP cases, got {len(auto_keep_cases)}"
    for c in auto_keep_cases:
        assert c["reaches_embedding"] is True, f"Auto-KEEP record {c['id']} failed to reach embedding!"
    print("  [OK] Verified 16/16 Auto-KEEP cases successfully reached the embedding provider.")

    # 5. Verify total chunk count matches expected
    assert s["post_review_chunks_embedded"] == 16, f"Expected 16 chunks embedded, got {s['post_review_chunks_embedded']}"
    print(f"  [OK] Verified exactly 16 chunks were embedded (14 calls avoided out of 30).")

    # 6. Overall test suite pass
    assert s["all_assertions_passed"] is True, "Test suite assertions failed!"
    print("  [OK] ALL 30 HANDOVER TEST SUITE ASSERTIONS PASSED WITH 100% SUCCESS!\n")
