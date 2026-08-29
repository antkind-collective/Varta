import os
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

def test_query(controller, query_text, test_name):
    print("\n" + "=" * 90)
    print(f"TEST: {test_name}")
    print(f"Query: \"{query_text}\"")
    print("=" * 90)

    start_time = time.time()
    session = controller.conversation_manager.create_session(f"sess_{int(time.time()*1000)}")
    resp = controller.process_query(query_text, session_id=session.session_id)
    duration = round(time.time() - start_time, 2)

    citations = resp.get("citations", [])
    answer = resp.get("answer") or resp.get("assistant_answer") or ""
    confidence = resp.get("confidence", {})

    print(f"\n[1] Retrieval & Citations ({len(citations)} sources):")
    seen_titles = set()
    has_duplicates = False
    for idx, c in enumerate(citations, 1):
        title = c.get("title") or "Untitled"
        doc_id = c.get("doc_id") or c.get("parent_doc_id") or ""
        score = c.get("similarity_score")
        print(f"  [{idx}] Score: {score} | ID: {doc_id} | Title: {title}")
        if title in seen_titles:
            has_duplicates = True
            print(f"       [ERROR] Duplicate Title Detected: '{title}'")
        seen_titles.add(title)

    print(f"\n  Duplicate Sources in Context: {'YES (FAIL)' if has_duplicates else 'NONE (PASS - 100% Unique)'}")

    print(f"\n[2] Model Confidence & Status:")
    print(f"  - Level: {confidence.get('level')}")
    print(f"  - Score: {confidence.get('score')}")
    print(f"  - LLM Invoked: {resp.get('llm_invoked', True)}")

    print(f"\n[3] Generated Answer ({duration}s):\n")
    print(answer)
    print("\n" + "-" * 90)

    return {
        "test": test_name,
        "query": query_text,
        "citations_count": len(citations),
        "has_duplicates": has_duplicates,
        "confidence_level": confidence.get("level"),
        "answer_snippet": answer[:200]
    }

def main():
    print("#" * 90)
    print("# VALIDATING RETRIEVAL DEDUPLICATION, THRESHOLDING & NATURAL AI REASONING")
    print("#" * 90)

    controller = get_assistant_controller()

    # 1. The failing example from user prompt
    test_query(
        controller,
        "did you process the disaster data from Reddit. in the file i just uploaded",
        "1. Failing Example Re-run (Reddit Disaster Data & Meta Inquiry)"
    )

    # 2. Genuine Gap / Out-of-Domain Query
    test_query(
        controller,
        "What are the semiconductor chip manufacturing policies in Taiwan?",
        "2. Genuine Gap / Out-Of-Domain Test (No Confident Padding)"
    )

    # 3. Domain Analytical Query
    test_query(
        controller,
        "What are the primary causes of flood devastation in Assam and what human activities worsen it?",
        "3. Domain Analytical Query (Assam Causes & Human Interventions)"
    )

    # 4. Domain Attribution Query
    test_query(
        controller,
        "Do people attribute disasters in Assam to God, nature, climate change, or human actions?",
        "4. Domain Attribution Query (Attribution & Belief Disentanglement)"
    )

if __name__ == "__main__":
    main()
