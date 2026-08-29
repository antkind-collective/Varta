import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.dependencies import get_assistant_controller
from src.llm_adapter import MockLLMAdapter
from src.context_relevance_engine import ContextRelevanceEngine

def run_trace(controller, query_text, session, label):
    print("\n" + "=" * 90)
    print(f"TRACE: {label}")
    print(f"Query: \"{query_text}\"")
    print("=" * 90)

    history = session.memory.get_history()
    print(f"[1] Conversation History turns: {len(history)}")

    # 1. Context Resolution & Query Rewriting
    rewrite_res = controller.query_rewriter.rewrite_query(query_text, history)
    rewritten_query = rewrite_res["rewritten_query"]
    research_ctx = rewrite_res.get("research_context")

    print(f"[2] Resolved Query & Context:")
    print(f"    - Rewritten Query: \"{rewritten_query}\"")
    print(f"    - Memory Used: {rewrite_res['memory_used']}")
    print(f"    - Resolution Method: {rewrite_res['resolution_method']}")
    if research_ctx:
        print(f"    - ResearchContext:")
        print(f"        * geography: {research_ctx.geography}")
        print(f"        * disaster_types: {research_ctx.disaster_types}")
        print(f"        * specific_location: '{getattr(research_ctx, 'specific_location', '')}'")
        print(f"        * custom_keywords: {research_ctx.custom_keywords}")
        print(f"        * research_topic: '{research_ctx.research_topic}'")
    else:
        print(f"    - ResearchContext: NONE")

    # 2. Plan Creation
    plan = controller.agent_planner.create_plan(
        query=query_text,
        rewritten_query=rewritten_query,
        memory_used=rewrite_res['memory_used'],
        history_count=len(history)
    )
    print(f"[3] Plan: Type={plan.plan_type}, Tool={plan.steps[0].get('tool_name') if plan.steps else None}")

    # 3. Vector Database Direct Retrieval Trace
    vdb = controller.rag_orchestrator.retriever.vector_db
    emb_provider = controller.rag_orchestrator.retriever.embedding_provider
    q_vec = emb_provider.embed_query(rewritten_query)
    
    raw_vdb_hits = vdb.search(query_vector=q_vec, top_k=5)
    print(f"\n[4] Vector DB Raw Search Hits (top 5 from 39,172 records without context filtering):")
    for idx, hit in enumerate(raw_vdb_hits):
        meta = hit.get("metadata", {})
        title = hit.get("title") or meta.get("title")
        pid = hit.get("post_id") or hit.get("parent_doc_id")
        score = hit.get("similarity_score")
        cat = meta.get("category_taxonomy") or hit.get("category_taxonomy")
        content_preview = (hit.get("content") or "")[:120].replace("\n", " ")
        print(f"    Hit {idx+1}: Score={score:.4f} | ID={pid} | Category='{cat}' | Title='{title}'")
        print(f"           Snippet: {content_preview}...")

    # 4. ContextRelevanceEngine Evaluation on retrieved documents
    rel_engine = ContextRelevanceEngine(embedding_provider=emb_provider)
    print(f"\n[5] ContextRelevanceEngine Evaluation of Top Hits against Active ResearchContext:")
    for idx, hit in enumerate(raw_vdb_hits):
        eval_res = rel_engine.evaluate_record(hit, context=research_ctx)
        print(f"    Doc {idx+1}: Decision={eval_res['relevance_decision']} | RelScore={eval_res['context_relevance_score']} | Reason={eval_res['relevance_reason']} | Title='{hit.get('title')}'")

    # 5. Full Controller Execution with Mock LLM
    controller.rag_orchestrator.llm_adapter = MockLLMAdapter()
    resp = controller.process_query(query_text, session_id=session.session_id)
    citations = resp.get("citations", [])
    print(f"\n[6] Final Context Blocks Passed to LLM:")
    for idx, cit in enumerate(citations):
        print(f"    Cit {idx+1}: Title='{cit.get('title')}' | Score={cit.get('similarity_score')} | URL={cit.get('source_url')}")

def main():
    controller = get_assistant_controller()
    
    # -------------------------------------------------------------
    # SCENARIO 1 & 2: User's Actual Failure Queries
    # -------------------------------------------------------------
    print("\n" + "#" * 90)
    print("# AUDITING OBSERVED FAILURES 1 & 2")
    print("#" * 90)
    
    sess_user = controller.conversation_manager.create_session("sess_audit_failures")
    
    q1 = "I want to only process Assam data, and tell what's the reason behind the causes happening in Assam, and what people thought of those - like they think it's by God or because of humans or what"
    run_trace(controller, q1, sess_user, "Turn 1: Complex Analytical Scope Query")

    q2 = "im talking about disasters"
    run_trace(controller, q2, sess_user, "Turn 2: Follow-up Correction Query")

    # -------------------------------------------------------------
    # SCENARIO 3: Tests A, B, C, D, E
    # -------------------------------------------------------------
    print("\n" + "#" * 90)
    print("# AUDITING REQUIRED TESTS A - E")
    print("#" * 90)

    tests = [
        ("TEST A", "What is the flood situation in Assam?"),
        ("TEST B", "What are the main causes of disasters in Assam?"),
        ("TEST C", "Do people attribute disasters in Assam to God, nature, climate change, or human actions?"),
        ("TEST D", "Which human activities are reported as contributing to disasters in Assam?"),
        ("TEST E", "Which districts in Assam were most affected by floods?")
    ]

    for label, q in tests:
        sess_t = controller.conversation_manager.create_session(f"sess_{label.lower().replace(' ', '_')}")
        run_trace(controller, q, sess_t, f"{label}: \"{q}\"")

if __name__ == "__main__":
    main()
