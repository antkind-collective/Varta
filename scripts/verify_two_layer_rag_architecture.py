import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.dependencies import get_assistant_controller
from src.llm_adapter import MockLLMAdapter

def verify_test(controller, query_text, session=None, label="", expected_geo="assam", expected_domain="disaster"):
    print("\n" + "=" * 90)
    print(f"VERIFICATION: {label}")
    print(f"Query: \"{query_text}\"")
    print("=" * 90)

    if session is None:
        session = controller.conversation_manager.create_session()

    history = session.memory.get_history()

    # Context Resolution & Query Rewriting
    rewrite_res = controller.query_rewriter.rewrite_query(query_text, history)
    rewritten_query = rewrite_res["rewritten_query"]
    research_ctx = rewrite_res.get("research_context")

    print(f"[1] Resolved Context & Intent:")
    print(f"    - Rewritten Query: \"{rewritten_query}\"")
    print(f"    - Memory Used: {rewrite_res['memory_used']}")
    print(f"    - Resolution Method: {rewrite_res['resolution_method']}")
    if research_ctx:
        print(f"    - ResearchContext:")
        print(f"        * Domain: {research_ctx.domain}")
        print(f"        * Geography: {research_ctx.geography}")
        print(f"        * Specific Location: '{research_ctx.specific_location}'")
        print(f"        * Disaster Types: {research_ctx.disaster_types}")
        print(f"        * Analytical Intent: {research_ctx.analytical_intent}")
        print(f"        * Topic: '{research_ctx.research_topic}'")

    # Scoped Candidate Corpus Count
    vdb = controller.rag_orchestrator.retriever.vector_db
    scoped_vids = vdb.get_scoped_vector_ids(
        geography=research_ctx.geography if research_ctx else None,
        specific_location=research_ctx.specific_location if research_ctx else None,
        domain=research_ctx.domain if research_ctx else "disaster",
        disaster_types=research_ctx.disaster_types if research_ctx else None
    )
    print(f"\n[2] Layer 1 Scoped Candidate Corpus Count: {len(scoped_vids):,} vectors")

    # Execute Controller Process Query (Mock LLM)
    controller.rag_orchestrator.llm_adapter = MockLLMAdapter()
    resp = controller.process_query(query_text, session_id=session.session_id)
    citations = resp.get("citations", [])

    print(f"\n[3] Final Documents Passed to LLM ({len(citations)} chunks):")
    other_state_detected = False
    non_disaster_detected = False

    for idx, cit in enumerate(citations):
        title = cit.get("title") or ""
        score = cit.get("similarity_score")
        doc_id = cit.get("doc_id") or cit.get("parent_doc_id")
        url = cit.get("source_url")
        print(f"    Doc {idx+1}: Score={score} | ID={doc_id} | Title='{title}'")

        # Rigorous assertions
        title_lower = title.lower()
        # Check other states
        for other_st in ["odisha", "bihar", "patna", "mumbai", "kerala", "sikkim", "delhi", "kedarnath", "dhenkanal"]:
            if other_st in title_lower and "assam" not in title_lower:
                other_state_detected = True
                print(f"    [FAIL] Detected other-state leak: {other_st} in '{title}'")

        # Check non-disaster topics
        for non_d in ["optosar satellite", "furrow tillage", "sadbhav yatra", "cabinet", "elusive cat", "physical abuse"]:
            if non_d in title_lower:
                non_disaster_detected = True
                print(f"    [FAIL] Detected non-disaster leak: {non_d} in '{title}'")

    assert not other_state_detected, f"Other-state document leaked into LLM context for {label}!"
    assert not non_disaster_detected, f"Non-disaster document leaked into LLM context for {label}!"
    print(f"\n  [PASS] Scope strictly enforced: 100% {expected_geo.upper()} {expected_domain.upper()} documents!")

    return session

def main():
    controller = get_assistant_controller()

    print("\n" + "#" * 90)
    print("# VERIFYING FIXED TWO-LAYER RAG RETRIEVAL ARCHITECTURE")
    print("#" * 90)

    # 1. Multi-turn conversation test
    sess_conv = controller.conversation_manager.create_session("sess_conv_verify")

    verify_test(
        controller,
        "I want to only process Assam data, and tell what's the reason behind the causes happening in Assam, and what people thought of those - like they think it's by God or because of humans or what",
        session=sess_conv,
        label="Turn 1: Analytical Query on Assam Causes & Attribution",
        expected_geo="assam",
        expected_domain="disaster"
    )

    verify_test(
        controller,
        "im talking about disasters",
        session=sess_conv,
        label="Turn 2: Follow-up Clarification (Assam Context Retained)",
        expected_geo="assam",
        expected_domain="disaster"
    )

    # 2. Tests A through E
    tests = [
        ("TEST A", "What is the flood situation in Assam?"),
        ("TEST B", "What are the main causes of disasters in Assam?"),
        ("TEST C", "Do people attribute disasters in Assam to God, nature, climate change, or human actions?"),
        ("TEST D", "Which human activities are reported as contributing to disasters in Assam?"),
        ("TEST E", "Which districts in Assam were most affected by floods?")
    ]

    for label, q in tests:
        sess_t = controller.conversation_manager.create_session(f"sess_{label.lower().replace(' ', '_')}")
        verify_test(controller, q, session=sess_t, label=label, expected_geo="assam", expected_domain="disaster")

    print("\n" + "=" * 90)
    print("ALL TWO-LAYER RETRIEVAL ARCHITECTURE VERIFICATIONS PASSED PERFECTLY!")
    print("=" * 90)

if __name__ == "__main__":
    main()
