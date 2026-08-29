import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.dependencies import get_assistant_controller

def audit_query(controller, query_text, session=None, label=""):
    print("\n" + "=" * 80)
    print(f"AUDIT RUN: {label}")
    print(f"Query: \"{query_text}\"")
    print("=" * 80)

    if session is None:
        session = controller.conversation_manager.create_session()

    history = session.memory.get_history()
    print(f"\n--- 1. Context Resolution & Query Rewriting ---")
    print(f"Session ID: {session.session_id}")
    print(f"Conversation History Length: {len(history)}")

    # Context resolution
    rewrite_res = controller.query_rewriter.rewrite_query(query_text, history)
    print(f"Rewritten Query: \"{rewrite_res['rewritten_query']}\"")
    print(f"Memory Used: {rewrite_res['memory_used']}")
    print(f"Resolution Method: {rewrite_res['resolution_method']}")
    
    ctx = rewrite_res.get("research_context")
    if ctx:
        print(f"Resolved ResearchContext:")
        print(f"  - disaster_types: {ctx.disaster_types}")
        print(f"  - geography: {ctx.geography}")
        print(f"  - specific_location: '{getattr(ctx, 'specific_location', '')}'")
        print(f"  - time_period: {ctx.time_period}")
        print(f"  - source_types: {ctx.source_types}")
        print(f"  - research_topic: '{ctx.research_topic}'")
        print(f"  - custom_keywords: {ctx.custom_keywords}")
    else:
        print("  - ResearchContext is NONE")

    # Check is_dataset_summary_query
    is_ds_summary = controller.rag_orchestrator.is_dataset_summary_query(query_text)
    print(f"\n--- 2. Dataset Summary Check ---")
    print(f"is_dataset_summary_query: {is_ds_summary}")

    # Planner
    print(f"\n--- 3. Agentic Planner & Tool Routing ---")
    plan = controller.agent_planner.create_plan(
        query=query_text,
        rewritten_query=rewrite_res['rewritten_query'],
        memory_used=rewrite_res['memory_used'],
        history_count=len(history)
    )
    print(f"Plan Type: {plan.plan_type}")
    print(f"Summary: {plan.summary_str()}")
    print(f"Tool Selection: {plan.steps[0].get('tool_name') if plan.steps else 'None'}")

    # Run the full controller process_query
    resp = controller.process_query(query_text, session_id=session.session_id)
    print(f"\n--- 4. Final Response Telemetry ---")
    print(f"Tool Selected: {resp.get('tool_selected')}")
    print(f"Confidence: {resp.get('confidence')}")

    # Check what citations / documents entered LLM
    citations = resp.get("citations", [])
    print(f"\n--- 5. Final Documents / Citations Passed to LLM ({len(citations)} docs) ---")
    for i, cit in enumerate(citations):
        print(f"\n  [Document {i+1}]")
        print(f"    Title: {cit.get('title')}")
        print(f"    Doc ID / Post ID: {cit.get('doc_id') or cit.get('parent_doc_id')}")
        print(f"    Similarity Score: {cit.get('similarity_score')}")
        print(f"    Source Type: {cit.get('source_type')}")
        print(f"    Source URL: {cit.get('source_url')}")

    print(f"\n--- 6. Assistant Answer Preview ---")
    print(resp.get("assistant_answer", "")[:300] + "...")

    return session

def run_all_audits():
    controller = get_assistant_controller()

    # AUDIT SCENARIO 1 & 2: User's Exact Two Turns
    print("\n" + "#" * 80)
    print("# AUDITING OBSERVED FAILURES 1 & 2")
    print("#" * 80)
    
    sess_user = controller.conversation_manager.create_session("sess_audit_user")
    
    q1 = "I want to only process Assam data, and tell what's the reason behind the causes happening in Assam, and what people thought of those - like they think it's by God or because of humans or what"
    audit_query(controller, q1, session=sess_user, label="OBSERVED FAILURE 1 (Turn 1)")

    q2 = "im talking about disasters"
    audit_query(controller, q2, session=sess_user, label="OBSERVED FAILURE 2 (Turn 2 Follow-up)")

    # AUDIT SCENARIO 3: Tests A, B, C, D, E
    print("\n" + "#" * 80)
    print("# AUDITING 5 REQUIRED TEST QUERIES (A, B, C, D, E)")
    print("#" * 80)

    tests = [
        ("TEST A", "What is the flood situation in Assam?"),
        ("TEST B", "What are the main causes of disasters in Assam?"),
        ("TEST C", "Do people attribute disasters in Assam to God, nature, climate change, or human actions?"),
        ("TEST D", "Which human activities are reported as contributing to disasters in Assam?"),
        ("TEST E", "Which districts in Assam were most affected by floods?")
    ]

    for label, q in tests:
        sess_t = controller.conversation_manager.create_session(f"sess_{label.lower().replace(' ', '_')}")
        audit_query(controller, q, session=sess_t, label=label)

if __name__ == "__main__":
    run_all_audits()
