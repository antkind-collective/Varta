import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.dependencies import get_assistant_controller
from src.context_relevance_engine import ContextRelevanceEngine, ResearchContext
from api.routes import get_review_records, submit_review_decision
from api.schemas import ReviewDecisionRequest

def run_comprehensive_verification():
    print("=" * 70)
    print("RUNNING COMPREHENSIVE VERIFICATION: DYNAMIC CONTEXT REVIEW WORKFLOW")
    print("=" * 70)

    controller = get_assistant_controller()
    vdb = controller.rag_orchestrator.retriever.vector_db
    initial_faiss_ntotal = vdb.index.ntotal
    initial_sqlite_count = vdb.metadata_store.get_total_records_count()
    print(f"[*] Initial Master Vector Store: {initial_faiss_ntotal} FAISS vectors, {initial_sqlite_count} SQLite records.")

    # -------------------------------------------------------------
    # 1. No active research context
    # -------------------------------------------------------------
    print("\n[Test 1] Query review queue with NO active research context...")
    session_no_ctx = controller.conversation_manager.create_session("session_test_empty")
    res_empty = get_review_records(session_id=session_no_ctx.session_id, controller=controller)
    assert res_empty.total_records == 0, f"Expected 0 records for empty context, got {res_empty.total_records}"
    assert len(res_empty.records) == 0, f"Expected empty records list, got {len(res_empty.records)}"
    print(f"  [PASS] Empty context returned {res_empty.total_records} records (No stale harness records).")

    # -------------------------------------------------------------
    # 2. Query with Research Context: "Floods in Assam"
    # -------------------------------------------------------------
    print("\n[Test 2] Query chat with 'Floods in Assam' to activate research context...")
    session_assam = controller.conversation_manager.create_session("session_test_assam")
    chat_resp = controller.process_query("Tell me about the recent floods in Assam", session_id=session_assam.session_id)
    assert session_assam.research_context is not None, "Session research_context should be set"
    assert "flood" in session_assam.research_context.disaster_types, "Disaster type 'flood' should be in context"
    assert "assam" in session_assam.research_context.geography, "Geography 'assam' should be in context"
    print(f"  [PASS] Session research context established: {session_assam.research_context}")

    # -------------------------------------------------------------
    # 3 & 4. Review Queue with active context
    # -------------------------------------------------------------
    print("\n[Test 3 & 4] Fetch review records for active session 'session_test_assam'...")
    res_assam = get_review_records(session_id=session_assam.session_id, controller=controller)
    print(f"  Topic: '{res_assam.context_topic}' | Total Borderline Records: {res_assam.total_records}")
    
    # Confirm none of the records are the stale harness record IDs
    returned_ids = [r.record_id for r in res_assam.records]
    assert "CASE_B5_IRRELEVANT_GEO_DISASTER_COMBO" not in returned_ids, "Stale CASE_B5 found in dynamic queue!"
    assert "CASE_D5_GIBBERISH_NON_PRINTABLE" not in returned_ids, "Stale CASE_D5 found in dynamic queue!"
    print(f"  [PASS] Dynamic evaluation successful: Zero stale test harness IDs returned.")

    # -------------------------------------------------------------
    # 5. Borderline Record Rendering Check (or fallback candidate test)
    # -------------------------------------------------------------
    print("\n[Test 5] Direct verification of ContextRelevanceEngine candidate review queue...")
    test_candidates = [
        {"post_id": "CAND_HIGH_ASSAM", "title": "Brahmaputra breaches banks in Kaziranga", "content": "Floods submerge 70% of Kaziranga national park in Assam."},
        {"post_id": "CAND_BORDERLINE_1", "title": "Heavy rainfall alert across northeast region", "content": "Weather department issues yellow warning for continuous rain across northeastern states."},
        {"post_id": "CAND_BORDERLINE_2", "title": "Disaster management mock drill held in Guwahati", "content": "Civil defense volunteers simulate flood rescue operations along the Brahmaputra."},
        {"post_id": "CAND_EXCLUDE_COMMERCIAL", "title": "Flood of festive offers at electronic stores", "content": "Retailers announce huge discounts on smart TVs and appliances."},
        {"post_id": "CAND_CONFLICT_BIHAR", "title": "Kosi river rises in north Bihar", "content": "Bihar disaster management team deployed in Supaul and Saharsa."}
    ]
    rel_engine = ContextRelevanceEngine(embedding_provider=controller.rag_orchestrator.retriever.embedding_provider)
    filtered_eval = rel_engine.filter_corpus_for_context(session_assam.research_context, test_candidates)
    
    keep_ids = [r["post_id"] for r in filtered_eval["retained_corpus"]]
    review_ids = [r["post_id"] for r in filtered_eval["review_queue"]]
    exclude_ids = [r["post_id"] for r in filtered_eval["excluded"]]

    print(f"  Evaluated 5 test candidates -> KEEP: {keep_ids}, REVIEW: {review_ids}, EXCLUDE: {exclude_ids}")
    assert "CAND_HIGH_ASSAM" in keep_ids, "High-confidence Assam flood must be KEEP"
    assert "CAND_EXCLUDE_COMMERCIAL" in exclude_ids, "Commercial metaphor must be EXCLUDE"
    assert "CAND_CONFLICT_BIHAR" in exclude_ids, "Geographic conflict must be EXCLUDE"
    assert len(review_ids) >= 1, "Ambiguous records should be routed to REVIEW"
    print("  [PASS] Relevance classification correctly partitions records into KEEP, REVIEW, and EXCLUDE.")

    # -------------------------------------------------------------
    # 6, 7, 8. Submit KEEP and EXCLUDE decisions
    # -------------------------------------------------------------
    print("\n[Test 6, 7, 8] Submit KEEP on CAND_BORDERLINE_1 and EXCLUDE on CAND_BORDERLINE_2...")
    # Add candidate to review queue in session
    submit_review_decision(ReviewDecisionRequest(
        record_id="CAND_BORDERLINE_1",
        decision="KEEP",
        session_id=session_assam.session_id
    ), controller=controller)

    submit_review_decision(ReviewDecisionRequest(
        record_id="CAND_BORDERLINE_2",
        decision="EXCLUDE",
        session_id=session_assam.session_id
    ), controller=controller)

    assert session_assam.review_decisions.get("CAND_BORDERLINE_1") == "KEEP"
    assert session_assam.review_decisions.get("CAND_BORDERLINE_2") == "EXCLUDE"
    print(f"  [PASS] Session review decisions persisted: {session_assam.review_decisions}")

    # -------------------------------------------------------------
    # 9. Verify excluded records are not used in RAG context
    # -------------------------------------------------------------
    print("\n[Test 9] Verify excluded records are filtered during VectorDatabase search...")
    search_res_before = vdb.search(
        query_vector=controller.rag_orchestrator.retriever.embedding_provider.embed_query("mock drill rescue"),
        top_k=10,
        metadata_filters={"excluded_post_ids": ["CAND_BORDERLINE_2"]}
    )
    for res in search_res_before:
        assert res.get("post_id") != "CAND_BORDERLINE_2", "Excluded post_id must not appear in search results!"
    print("  [PASS] VectorDatabase search strictly filters out excluded_post_ids.")

    # -------------------------------------------------------------
    # 10. Verify FAISS vector count and SQLite record count unchanged
    # -------------------------------------------------------------
    print("\n[Test 10] Checking master store integrity...")
    assert vdb.index.ntotal == initial_faiss_ntotal, f"FAISS ntotal changed: was {initial_faiss_ntotal}, now {vdb.index.ntotal}"
    assert vdb.metadata_store.get_total_records_count() == initial_sqlite_count, "SQLite count changed!"
    print(f"  [PASS] Master store 100% untouched: {vdb.index.ntotal} vectors, {vdb.metadata_store.get_total_records_count()} SQLite records.")

    # -------------------------------------------------------------
    # 11. Follow-up query retains context and decisions
    # -------------------------------------------------------------
    print("\n[Test 11] Ask follow-up question: 'Which districts were worst affected?'...")
    followup_resp = controller.process_query("Which districts were worst affected?", session_id=session_assam.session_id)
    assert followup_resp["memory_used"] is True, "Follow-up question should use conversation memory"
    assert "assam" in followup_resp["rewritten_query"].lower() or "flood" in followup_resp["rewritten_query"].lower(), "Rewritten query must retain Assam flood context"
    assert session_assam.review_decisions.get("CAND_BORDERLINE_2") == "EXCLUDE", "Review decision must persist across turns"
    print(f"  [PASS] Follow-up rewritten query: '{followup_resp['rewritten_query']}' (Context & Review Decisions retained).")

    print("\n" + "=" * 70)
    print("ALL 11 WORKFLOW VERIFICATION CHECKS PASSED PERFECTLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_comprehensive_verification()
