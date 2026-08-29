import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.dependencies import get_assistant_controller

def analyze():
    controller = get_assistant_controller()
    retriever = controller.rag_orchestrator.retriever

    queries = [
        ("Query A (Meta/Reddit Query from Failure Example)", "did you process the disaster data from Reddit. in the file i just uploaded"),
        ("Query B (Relevant Domain Query - Assam Floods)", "What is the flood situation in Assam?"),
        ("Query C (Relevant Analytical Query - Causes/Attribution)", "What are the causes of disasters in Assam and how do human activities worsen them?"),
        ("Query D (Completely Out-Of-Domain - Taiwan Semiconductor)", "What are the semiconductor chip manufacturing policies in Taiwan?"),
        ("Query E (Completely Out-Of-Domain - Quantum Computing)", "How does Shor's algorithm factor large integers in polynomial time?")
    ]

    for label, q in queries:
        print("\n" + "=" * 85)
        print(f"{label}")
        print(f"Query: \"{q}\"")
        print("=" * 85)
        
        res = retriever.retrieve(q, top_k=8)
        results = res.get("results", [])
        if not results:
            print("  No results returned.")
            continue

        scores = [r["similarity_score"] for r in results]
        print(f"Score Summary -> Min: {min(scores):.4f} | Max (Top 1): {max(scores):.4f} | Avg: {sum(scores)/len(scores):.4f}\n")
        for idx, r in enumerate(results, 1):
            title = r.get("title") or "Untitled"
            parent_id = r.get("parent_doc_id") or ""
            score = r.get("similarity_score", 0.0)
            print(f"  [{idx}] Score: {score:.4f} | ID: {parent_id} | Title: {title[:75]}")

if __name__ == "__main__":
    analyze()
