import sys
import json
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from api.dependencies import get_assistant_controller

def test_queries():
    print("=" * 90)
    print("VARTA LIVE QnA SUITE & REGRESSION VERIFICATION")
    print("=" * 90)

    controller = get_assistant_controller()

    test_cases = [
        ("Query 1: Original Failing Meta/Reddit Query", "did you process the disaster data from Reddit. in the file i just uploaded"),
        ("Query 2: Assam Flood Situation (Strong Domain Query)", "What is the flood situation in Assam?"),
        ("Query 3: Most Affected Assam Districts (Strong Domain Query)", "Which districts in Assam were most affected by floods?"),
        ("Query 4: Assam Disaster Causes (Strong Analytical Query)", "What are the main causes of disasters in Assam?"),
        ("Query 5: Bihar / Patna Floods (Alternative Regional Domain Query)", "What is the flood situation in Patna and Bihar?")
    ]

    for label, q in test_cases:
        print("\n" + "=" * 90)
        print(f"[{label}]")
        print(f"Query Text: \"{q}\"")
        print("-" * 90)

        session = controller.conversation_manager.create_session(f"sess_{int(time.time()*1000)}")
        start_time = time.time()
        resp = controller.process_query(q, session_id=session.session_id)
        duration = round(time.time() - start_time, 2)

        answer = resp.get("answer") or resp.get("assistant_answer") or ""
        citations = resp.get("citations", [])
        confidence = resp.get("confidence", {})

        print(f"Latency: {duration}s | Confidence: {confidence.get('level')} (Score: {confidence.get('score')}) | LLM Invoked: {resp.get('llm_invoked', True)}")
        print(f"Citations Retrieved: {len(citations)}")
        for idx, c in enumerate(citations, 1):
            title = c.get("title") or "Untitled"
            doc_id = c.get("doc_id") or c.get("parent_doc_id") or ""
            score = c.get("similarity_score")
            print(f"   [{idx}] Score: {score} | Title: '{title[:70]}' | ID: {doc_id}")

        print(f"\nExact Answer Text:\n")
        print(answer)
        print("\n" + "=" * 90)

if __name__ == "__main__":
    test_queries()
