import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.dependencies import get_assistant_controller, reload_assistant_controller

def run_multi_turn_test():
    print("=" * 80, flush=True)
    print("MULTI-TURN CONVERSATION SEQUENCE VALIDATION", flush=True)
    print("=" * 80, flush=True)

    reload_assistant_controller()
    controller = get_assistant_controller()
    session_id = "test_multi_turn_seq_session"

    test_queries = [
        # Turn 1: The first user query reported in bug
        (
            1,
            "Is there a difference between how officials or media describe the disaster response and how it's actually being experienced by affected communities?",
            "direct", # Should NOT be mangled into comparison or sub-splits
            False # memory not used
        ),
        # Turn 2: The second user query reported in bug
        (
            2,
            "Are there any government policies or programs mentioned in the coverage that don't seem to come up when people talk about their actual experience?",
            "direct", # Should NOT be mangled, should NOT concatenate with Turn 1
            False # memory not used (standalone analytical query)
        ),
        # Turn 3: Clear entity query
        (
            3,
            "Tell me about the flood situation in Assam.",
            "direct",
            False
        ),
        # Turn 4: Genuine follow-up missing entity -> should resolve entity carry-over
        (
            4,
            "Which districts are worst affected?",
            "followup",
            True # memory used
        ),
        # Turn 5: Genuine entity switch follow-up
        (
            5,
            "What about Patna?",
            "followup",
            True # memory used
        ),
        # Turn 6: Genuine explicit comparison between two clean entities
        (
            6,
            "Compare the flood impacts in Assam and Bihar",
            "comparison",
            False
        )
    ]

    for turn_idx, query, expected_plan_type, expected_memory_used in test_queries:
        print(f"\n" + "-" * 80, flush=True)
        print(f"TURN {turn_idx}: \"{query}\"", flush=True)
        print("-" * 80, flush=True)

        res = controller.process_query(query=query, session_id=session_id)
        
        plan_type = res.get("plan_type")
        rewritten = res.get("rewritten_query")
        memory_used = res.get("memory_used")
        answer = res.get("assistant_answer") or res.get("answer", "")
        plan_summary = res.get("plan_summary")
        citations = res.get("citations", [])

        print(f"  Plan Type: {plan_type} (Expected: {expected_plan_type})", flush=True)
        print(f"  Memory Used: {memory_used} (Expected: {expected_memory_used})", flush=True)
        print(f"  Rewritten Query: \"{rewritten}\"", flush=True)
        print(f"  Plan Summary: {plan_summary}", flush=True)
        print(f"  Citations Returned: {len(citations)}", flush=True)
        print(f"  Answer Preview (first 200 chars):\n    {answer[:200]}...", flush=True)

        # Assertions
        assert "continuous field monitoring and relief operations remain in effect" not in answer, \
            f"Turn {turn_idx} output contained stale hardcoded boilerplate!"
        assert "Key Similarities & Differences" not in answer or expected_plan_type == "comparison", \
            f"Turn {turn_idx} used comparison template incorrectly!"
        assert plan_type == expected_plan_type, \
            f"Turn {turn_idx} expected plan_type {expected_plan_type}, got {plan_type}"

        # Turn 2 specific check: must NOT have Turn 1 query concatenated into it
        if turn_idx == 2:
            assert "Is there a difference between how officials" not in rewritten, \
                "Turn 2 query was corrupted by Turn 1 text!"
            assert "disasters in Is there" not in rewritten, \
                "Turn 2 query was mangled with 'disasters in Is there'!"

        # Turn 4 specific check: must have Assam resolved
        if turn_idx == 4:
            assert "Assam" in rewritten or "assam" in rewritten.lower(), \
                f"Turn 4 failed to carry over Assam: '{rewritten}'"

        # Turn 5 specific check: must have Patna resolved
        if turn_idx == 5:
            assert "Patna" in rewritten, \
                f"Turn 5 failed to resolve Patna: '{rewritten}'"

    print("\n" + "=" * 80, flush=True)
    print("ALL 6 MULTI-TURN SEQUENTIAL TEST CASES PASSED PERFECTLY!", flush=True)
    print("=" * 80, flush=True)

if __name__ == "__main__":
    run_multi_turn_test()
