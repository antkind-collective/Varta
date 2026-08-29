import sys
import json
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "https://varta-production-c8d8.up.railway.app"

def main():
    print("=" * 80)
    print(f"TESTING LIVE RAILWAY PRODUCTION ENDPOINT: {BASE_URL}")
    print("=" * 80)

    # 1. Health check / Root check
    try:
        req = urllib.request.Request(f"{BASE_URL}/", headers={"User-Agent": "Varta-Validator"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[Health Check] HTTP Status: {resp.status} (App is live and running)")
    except Exception as e:
        print(f"[Health Check] Error: {e}")

    # 2. Session Creation
    try:
        req_session = urllib.request.Request(
            f"{BASE_URL}/session",
            data=json.dumps({}).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "Varta-Validator"}
        )
        with urllib.request.urlopen(req_session, timeout=20) as resp:
            sess_data = json.loads(resp.read().decode("utf-8"))
            session_id = sess_data.get("session_id")
            print(f"[Session Created] ID: {session_id}")
    except Exception as e:
        print(f"[Session Creation Failed]: {e}")
        return

    def ask(query_text, label):
        print("\n" + "=" * 80)
        print(f"[{label}]")
        print(f"Query: \"{query_text}\"")
        print("-" * 80)
        
        req_chat = urllib.request.Request(
            f"{BASE_URL}/chat",
            data=json.dumps({"session_id": session_id, "message": query_text}).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "Varta-Validator"}
        )
        start_t = time.time()
        with urllib.request.urlopen(req_chat, timeout=90) as resp:
            duration = round(time.time() - start_t, 2)
            chat_resp = json.loads(resp.read().decode("utf-8"))
            answer = chat_resp.get("answer") or chat_resp.get("assistant_answer") or ""
            citations = chat_resp.get("citations", [])
            conf = chat_resp.get("confidence", {})

            print(f"Latency: {duration}s | Confidence: {conf.get('level')} (Score: {conf.get('score')}) | Citations: {len(citations)}")
            for idx, c in enumerate(citations, 1):
                print(f"   [{idx}] Score: {c.get('similarity_score')} | Title: '{c.get('title')}' | ID: {c.get('doc_id') or c.get('parent_doc_id')}")

            print(f"\nExact Production Response:\n")
            print(answer)
            print("-" * 80)

    # Test 1: Failing Example
    ask("did you process the disaster data from Reddit. in the file i just uploaded", "1. Original Failing Query (Reddit / File upload)")

    # Test 2: Strong Domain Query
    ask("What is the flood situation in Assam?", "2. Strong Domain Query (Assam Floods)")

if __name__ == "__main__":
    main()
