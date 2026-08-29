import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.dependencies import get_assistant_controller

def reproduce_bug():
    controller = get_assistant_controller()
    
    q1 = "Is there a difference between how officials or media describe the disaster response and how it's actually being experienced by affected communities?"
    q2 = "Are there any government policies or programs mentioned in the coverage that don't seem to come up when people talk about their actual experience?"

    session_id = "test_bug_session_1"
    
    print("=" * 80)
    print("STEP 1: RUNNING QUERY 1")
    print("=" * 80)
    res1 = controller.process_query(query=q1, session_id=session_id)
    print("Q1 Plan Type:", res1.get("plan_type"))
    print("Q1 Plan Summary:", res1.get("plan_summary"))
    print("Q1 Answer:\n", res1.get("answer"))

    print("\n" + "=" * 80)
    print("STEP 2: RUNNING QUERY 2")
    print("=" * 80)
    res2 = controller.process_query(query=q2, session_id=session_id)
    print("Q2 Plan Type:", res2.get("plan_type"))
    print("Q2 Plan Summary:", res2.get("plan_summary"))
    print("Q2 Rewritten Query:", res2.get("rewritten_query"))
    print("Q2 Answer:\n", res2.get("answer"))

if __name__ == "__main__":
    reproduce_bug()
