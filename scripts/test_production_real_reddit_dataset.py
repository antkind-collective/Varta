import sys
import urllib.request
import json
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

PROD_URL = "https://varta-production-c8d8.up.railway.app"

def test_production_reddit():
    print("=" * 80)
    print("PRODUCTION DATASET VERIFICATION & LIVE TESTING")
    print("=" * 80)

    # 1. Check Ingestion Status
    req = urllib.request.Request(f"{PROD_URL}/dataset/status")
    status_resp = json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8"))
    print("\n[1] Ingestion Status from Production:")
    print(json.dumps(status_resp, indent=2))

    # 2. Initialize Session
    req_sess = urllib.request.Request(f"{PROD_URL}/session", data=b"", headers={"Content-Type": "application/json"})
    sess_data = json.loads(urllib.request.urlopen(req_sess, timeout=10).read().decode("utf-8"))
    session_id = sess_data["session_id"]
    print(f"\n[2] Initialized Session: {session_id}")

    # 3. Test Scoped Query on Reddit Dataset
    print("\n" + "=" * 80)
    print("[3] Running Query on Reddit Dataset")
    print("=" * 80)
    scoped_payload = {
        "message": "What are Reddit users discussing regarding flood relief, mutual aid, waterlogging, or rescue efforts in the disaster data?",
        "session_id": session_id
    }
    req_scoped = urllib.request.Request(
        f"{PROD_URL}/chat",
        data=json.dumps(scoped_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    start = time.time()
    resp_scoped = json.loads(urllib.request.urlopen(req_scoped, timeout=60).read().decode("utf-8"))
    elapsed_scoped = round(time.time() - start, 2)

    print(f"Latency: {elapsed_scoped}s")
    print(f"Plan Type: {resp_scoped.get('plan_type')}")
    print(f"Tool Used: {resp_scoped.get('tool_used')}")
    print(f"Assistant Answer:\n{resp_scoped.get('answer')}")
    print("\nCitations Returned:")
    for c in resp_scoped.get("citations", []):
        print(f"  - [{c.get('citation_id')}] (Score: {c.get('similarity_score')}): {c.get('title')} | URL: {c.get('source_url')} | DocID: {c.get('doc_id')} | Source: {c.get('source_type')}")

    # 4. Test News / Master Corpus Query in separate session
    print("\n" + "=" * 80)
    print("[4] Running Query on News Corpus (Flood situation in Assam)")
    print("=" * 80)
    req_sess2 = urllib.request.Request(f"{PROD_URL}/session", data=b"", headers={"Content-Type": "application/json"})
    sess_data2 = json.loads(urllib.request.urlopen(req_sess2, timeout=10).read().decode("utf-8"))
    session_id2 = sess_data2["session_id"]

    unscoped_payload = {
        "message": "What is the flood situation in Assam according to regional news reports?",
        "session_id": session_id2
    }
    req_unscoped = urllib.request.Request(
        f"{PROD_URL}/chat",
        data=json.dumps(unscoped_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    start = time.time()
    resp_unscoped = json.loads(urllib.request.urlopen(req_unscoped, timeout=60).read().decode("utf-8"))
    elapsed_unscoped = round(time.time() - start, 2)

    print(f"Latency: {elapsed_unscoped}s")
    print(f"Plan Type: {resp_unscoped.get('plan_type')}")
    print(f"Assistant Answer:\n{resp_unscoped.get('answer')}")
    print("\nCitations Returned:")
    for c in resp_unscoped.get("citations", []):
        print(f"  - [{c.get('citation_id')}] (Score: {c.get('similarity_score')}): {c.get('title')} | URL: {c.get('source_url')} | DocID: {c.get('doc_id')} | Source: {c.get('source_type')}")

if __name__ == "__main__":
    test_production_reddit()
