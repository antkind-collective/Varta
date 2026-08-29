import urllib.request
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

PROD_URL = "https://varta-production-c8d8.up.railway.app"

queries = [
    "How do communities prepare for floods and what mutual aid is organized?",
    "Do people rely more on government aid or community support during disasters?",
    "What is the representation of women and vulnerable groups in disaster response?"
]

for q in queries:
    print("=" * 80)
    print(f"QUERY: {q}")
    print("=" * 80)
    # create session
    req_s = urllib.request.Request(f"{PROD_URL}/session", data=b"", headers={"Content-Type": "application/json"})
    sess_id = json.loads(urllib.request.urlopen(req_s, timeout=10).read().decode("utf-8"))["session_id"]
    
    payload = {"message": q, "session_id": sess_id}
    req = urllib.request.Request(f"{PROD_URL}/chat", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
    
    print("Plan:", resp.get("plan_type"))
    print("Citations:")
    for c in resp.get("citations", []):
        print(f"  - [{c.get('citation_id')}] (Score: {c.get('similarity_score')}): {c.get('title')} | URL: {c.get('source_url')}")
    print("\nAnswer preview:", (resp.get("answer") or "")[:200])
