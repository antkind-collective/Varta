import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from api.app import app

def test_dataset_selection():
    client = TestClient(app)
    
    print("=" * 80)
    print("TESTING /datasets/list ENDPOINT")
    print("=" * 80)
    resp = client.get("/datasets/list")
    assert resp.status_code == 200, f"Failed: {resp.text}"
    data = resp.json()
    print("Datasets List Response:")
    print(data)
    
    dataset_tags = [d["source_dataset"] for d in data["datasets"]]
    assert "master_news_corpus" in dataset_tags, "master_news_corpus missing"
    assert "sagar_reddit_dataset" in dataset_tags, "sagar_reddit_dataset missing"
    
    # Confirm friendly display names
    for d in data["datasets"]:
        if d["source_dataset"] == "sagar_reddit_dataset":
            print(f"Verified Sagar display name: {d['display_name']} ({d['chunk_count']} chunks)")
            assert "Reddit" in d["display_name"]
        elif d["source_dataset"] == "master_news_corpus":
            print(f"Verified Master display name: {d['display_name']} ({d['chunk_count']} chunks)")
            assert "Master News Corpus" == d["display_name"]
            
    print("\n" + "=" * 80)
    print("TESTING SCOPED QUERY: sagar_reddit_dataset")
    print("=" * 80)
    # Session 1: Scoped to sagar_reddit_dataset
    s_resp = client.post("/session")
    session_id_1 = s_resp.json()["session_id"]
    
    chat_resp_1 = client.post("/chat", json={
        "message": "Is it safe to travel to Munnar or Ooty in August amidst recent rainfall and landslides according to Reddit discussions?",
        "session_id": session_id_1,
        "dataset_filter": ["sagar_reddit_dataset"]
    })
    assert chat_resp_1.status_code == 200, f"Chat failed: {chat_resp_1.text}"
    cdata_1 = chat_resp_1.json()
    print(f"Plan Type: {cdata_1.get('plan_type')}")
    print(f"Answer Preview: {cdata_1.get('answer')[:200]}...")
    print(f"Citations Count: {len(cdata_1.get('citations', []))}")
    assert len(cdata_1.get("citations", [])) > 0, "Expected citations from sagar_reddit_dataset"
    for idx, cit in enumerate(cdata_1.get("citations", []), 1):
        print(f"  [{idx}] doc_id={cit.get('doc_id')}, title={cit.get('title')}, url={cit.get('source_url')}")
            
    print("\n" + "=" * 80)
    print("TESTING SCOPED QUERY: master_news_corpus")
    print("=" * 80)
    # Session 2: Scoped to master_news_corpus
    s_resp_2 = client.post("/session")
    session_id_2 = s_resp_2.json()["session_id"]
    
    chat_resp_2 = client.post("/chat", json={
        "message": "What is the official flood situation in Assam and NDRF deployment?",
        "session_id": session_id_2,
        "dataset_filter": ["master_news_corpus"]
    })
    assert chat_resp_2.status_code == 200, f"Chat failed: {chat_resp_2.text}"
    cdata_2 = chat_resp_2.json()
    print(f"Plan Type: {cdata_2.get('plan_type')}")
    print(f"Answer Preview: {cdata_2.get('answer')[:200]}...")
    print(f"Citations Count: {len(cdata_2.get('citations', []))}")
    for idx, cit in enumerate(cdata_2.get("citations", []), 1):
        print(f"  [{idx}] doc_id={cit.get('doc_id')}, source_dataset={cit.get('source_dataset')}, url={cit.get('source_url')}")
        if cit.get('source_dataset'):
            assert cit.get('source_dataset') == 'master_news_corpus', f"Expected master_news_corpus but got {cit.get('source_dataset')}"

    print("\n" + "=" * 80)
    print("TESTING UNSCOPED QUERY: ALL DATASETS")
    print("=" * 80)
    # Session 3: Unscoped query
    s_resp_3 = client.post("/session")
    session_id_3 = s_resp_3.json()["session_id"]
    
    chat_resp_3 = client.post("/chat", json={
        "message": "Give an overview of recent disaster damages in India.",
        "session_id": session_id_3,
        "dataset_filter": None
    })
    assert chat_resp_3.status_code == 200, f"Chat failed: {chat_resp_3.text}"
    cdata_3 = chat_resp_3.json()
    print(f"Plan Type: {cdata_3.get('plan_type')}")
    print(f"Answer Preview: {cdata_3.get('answer')[:200]}...")
    print(f"Citations Count: {len(cdata_3.get('citations', []))}")
    for idx, cit in enumerate(cdata_3.get("citations", []), 1):
        print(f"  [{idx}] doc_id={cit.get('doc_id')}, source_dataset={cit.get('source_dataset')}")
        
    print("\n" + "=" * 80)
    print("ALL DATASET SELECTION & SCOPED RETRIEVAL TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    test_dataset_selection()
