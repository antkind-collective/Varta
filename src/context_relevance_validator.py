import os
import json
import logging
from typing import Dict, Any, List
from src.context_relevance_engine import ContextRelevanceEngine, ResearchContext

logger = logging.getLogger("ContextRelevanceValidator")

class ContextRelevanceValidator:
    """
    Validation Suite for VARTA Context-Driven Corpus Filtering Layer.
    Validates all 8 core functional scenarios:
    1. Clearly relevant document -> KEEP
    2. Clearly irrelevant document -> EXCLUDE
    3. Keyword-present but contextually irrelevant (metaphor/commercial) -> REVIEW / EXCLUDE
    4. Keyword-absent but semantically relevant document -> KEEP
    5. Duplicate / empty / malformed document -> EXCLUDE
    6. Missing URL but otherwise relevant document -> KEEP (Proves URL absence is not content irrelevance)
    7. Mixed relevance dataset batch processing
    8. Correct KEEP/REVIEW/EXCLUDE decisions and score range bounds [0.0, 1.0]
    """

    def __init__(self):
        self.engine = ContextRelevanceEngine()
        self.context = ResearchContext(
            disaster_types=["flood", "heavy rainfall", "inundation", "monsoon", "river overflow", "बाढ़"],
            geography=["bihar", "assam", "patna", "mumbai", "india", "बिहार", "असम"],
            source_types=["News", "Official Report", "Research"],
            research_topic="Disaster management, flood monitoring, heavy rainfall impact, river inundation, and emergency relief operations in India."
        )

    def run_all_checks(self) -> Dict[str, Any]:
        results = []

        # Check 1: Clearly relevant document
        doc1 = {
            "post_id": "https://www.amarujala.com/bihar/patna/flood-news.1",
            "title": "Bihar Flood Alert: Ganga River Crosses Danger Mark in Patna",
            "text_content": "Heavy monsoon downpour triggered severe inundation across North Bihar. Over 10 districts affected as Ganga river water level surges above danger level.",
            "source_type": "News",
            "category_taxonomy": "Disaster | Flood"
        }
        res1 = self.engine.evaluate_record(doc1, self.context)
        check1_pass = res1["relevance_decision"] == "KEEP" and res1["context_relevance_score"] >= 0.60
        results.append({
            "check": "1. Clearly Relevant Document",
            "passed": check1_pass,
            "decision": res1["relevance_decision"],
            "score": res1["context_relevance_score"],
            "reason": res1["relevance_reason"]
        })

        # Check 2: Clearly irrelevant document
        doc2 = {
            "post_id": "https://sports.example.com/cricket/world-cup-final",
            "title": "India Wins T20 Cricket World Cup Final in Barbados",
            "text_content": "India defeated South Africa by 7 runs in a thrilling T20 World Cup final. Virat Kohli and Jasprit Bumrah produced stellar performances.",
            "source_type": "News",
            "category_taxonomy": "Sports | Cricket"
        }
        res2 = self.engine.evaluate_record(doc2, self.context)
        check2_pass = res2["relevance_decision"] == "EXCLUDE" and res2["context_relevance_score"] < 0.35
        results.append({
            "check": "2. Clearly Irrelevant Document",
            "passed": check2_pass,
            "decision": res2["relevance_decision"],
            "score": res2["context_relevance_score"],
            "reason": res2["relevance_reason"]
        })

        # Check 3: Keyword-present but contextually irrelevant (metaphor / tech sales)
        doc3 = {
            "post_id": "https://tech.example.com/iphone-launch-sales",
            "title": "Tech Store Reports Flood of New iPhone Sales and Massive Online Offers",
            "text_content": "Retailers experienced a flood of customer inquiries and online sales after the new smartphone launch. Discount offers drove record order volume.",
            "source_type": "News",
            "category_taxonomy": "Technology | E-commerce"
        }
        res3 = self.engine.evaluate_record(doc3, self.context)
        check3_pass = res3["relevance_decision"] in ("REVIEW", "EXCLUDE") and res3["evaluation_details"]["metaphor_detected"] is True
        results.append({
            "check": "3. Keyword-Present but Contextually Irrelevant (Metaphor)",
            "passed": check3_pass,
            "decision": res3["relevance_decision"],
            "score": res3["context_relevance_score"],
            "reason": res3["relevance_reason"]
        })

        # Check 4: Keyword-absent but semantically relevant document
        doc4 = {
            "post_id": "https://news.example.com/monsoon-inundation-bihar",
            "title": "Rivers Surge After Torrential Downpour in Northern Districts",
            "text_content": "Monsoon rains submerged agricultural land and inundated low-lying residential areas in Kosi basin. Local administration deployed NDRF boats and distributed ration packets.",
            "source_type": "News",
            "category_taxonomy": "Environment | Monsoon"
        }
        res4 = self.engine.evaluate_record(doc4, self.context)
        check4_pass = res4["relevance_decision"] == "KEEP" and res4["relevance_reason"] == "KEEP_SEMANTIC_MATCH_NO_EXPLICIT_KEYWORD"
        results.append({
            "check": "4. Keyword-Absent but Semantically Relevant Document",
            "passed": check4_pass,
            "decision": res4["relevance_decision"],
            "score": res4["context_relevance_score"],
            "reason": res4["relevance_reason"]
        })

        # Check 5: Duplicate / empty / malformed document
        doc5 = {
            "post_id": "doc_empty",
            "title": "",
            "text_content": "   ",
            "source_type": "News"
        }
        res5 = self.engine.evaluate_record(doc5, self.context)
        check5_pass = res5["relevance_decision"] == "EXCLUDE" and res5["data_quality_score"] == 0.0
        results.append({
            "check": "5. Duplicate / Empty / Malformed Document",
            "passed": check5_pass,
            "decision": res5["relevance_decision"],
            "score": res5["context_relevance_score"],
            "reason": res5["relevance_reason"]
        })

        # Check 6: Missing URL but otherwise relevant document
        doc6 = {
            "post_id": None,
            "source_url": None,
            "title": "Assam Flood Situation: Brahmaputra River Water Levels Rise Above Warning Mark",
            "text_content": "Heavy monsoon rainfall triggered widespread flooding across 15 Assam districts. Embankments breached in Kaziranga National Park area.",
            "source_type": "News",
            "category_taxonomy": "Disaster | Flood"
        }
        res6 = self.engine.evaluate_record(doc6, self.context)
        check6_pass = res6["relevance_decision"] == "KEEP" and "MISSING_URL" in res6["evaluation_details"]["quality_flags"]
        results.append({
            "check": "6. Missing URL but Otherwise Relevant Document",
            "passed": check6_pass,
            "decision": res6["relevance_decision"],
            "score": res6["context_relevance_score"],
            "reason": res6["relevance_reason"]
        })

        # Check 7: Mixed relevance dataset batch processing
        dataset_sample = [doc1, doc2, doc3, doc4, doc5, doc6]
        filtered_batch, stats = self.engine.filter_dataset(dataset_sample, context=self.context, allowed_decisions=("KEEP", "REVIEW"))
        check7_pass = stats["total_inspected"] == 6 and stats["total_excluded"] >= 2 and stats["total_passed"] >= 3
        results.append({
            "check": "7. Mixed Relevance Dataset Batch Processing",
            "passed": check7_pass,
            "stats": stats
        })

        # Check 8: Correct KEEP / REVIEW / EXCLUDE boundary & score range enforcement
        check8_pass = True
        for res in [res1, res2, res3, res4, res5, res6]:
            if not (0.0 <= res["context_relevance_score"] <= 1.0) or not (0.0 <= res["data_quality_score"] <= 1.0):
                check8_pass = False
            if res["relevance_decision"] not in ("KEEP", "REVIEW", "EXCLUDE"):
                check8_pass = False
        results.append({
            "check": "8. Score Boundary [0.0, 1.0] and Decision Enum Compliance",
            "passed": check8_pass
        })

        total_checks = len(results)
        passed_checks = sum(1 for r in results if r["passed"])
        compliance_pct = round((passed_checks / total_checks) * 100, 2)

        return {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "compliance_pct": compliance_pct,
            "details": results
        }
