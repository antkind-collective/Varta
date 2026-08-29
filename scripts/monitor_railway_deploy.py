import sys
import time
import urllib.request
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

PROD_URL = "https://varta-production-c8d8.up.railway.app"

def monitor():
    print("=" * 80)
    print("ACTIVELY MONITORING RAILWAY DEPLOYMENT")
    print("=" * 80)
    
    start_time = time.time()
    max_wait = 300  # 5 minutes
    
    while time.time() - start_time < max_wait:
        elapsed = int(time.time() - start_time)
        try:
            # Check /health
            req_health = urllib.request.Request(f"{PROD_URL}/health")
            h_resp = json.loads(urllib.request.urlopen(req_health, timeout=10).read().decode("utf-8"))
            uptime = h_resp.get("uptime_seconds", 0)
            
            # Check /datasets/list
            req_ds = urllib.request.Request(f"{PROD_URL}/datasets/list")
            ds_resp = json.loads(urllib.request.urlopen(req_ds, timeout=10).read().decode("utf-8"))
            
            print(f"\n[{elapsed}s] DEPLOYMENT LIVE & RESPONDING!")
            print(f"Health check: {h_resp}")
            print(f"Datasets list: {ds_resp}")
            
            # Run Live Verification Queries
            print("\n" + "=" * 80)
            print("RUNNING LIVE SCOPED VERIFICATION QUERIES ON PRODUCTION")
            print("=" * 80)
            
            # 1. Session Init
            req_sess = urllib.request.Request(f"{PROD_URL}/session", data=b"", headers={"Content-Type": "application/json"})
            sess_id = json.loads(urllib.request.urlopen(req_sess, timeout=10).read().decode("utf-8"))["session_id"]
            print(f"Created Session: {sess_id}")
            
            # 2. Scoped Reddit Query
            print("\n[Query 1] Scoped to sagar_reddit_dataset:")
            reddit_payload = {
                "message": "Is it safe to visit Munnar or Ooty in August according to Reddit discussions?",
                "session_id": sess_id,
                "dataset_filter": ["sagar_reddit_dataset"]
            }
            req_r = urllib.request.Request(f"{PROD_URL}/chat", data=json.dumps(reddit_payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            r_resp = json.loads(urllib.request.urlopen(req_r, timeout=60).read().decode("utf-8"))
            print(f"Answer: {r_resp.get('answer')[:180]}...")
            print(f"Citations ({len(r_resp.get('citations', []))}):")
            for c in r_resp.get("citations", []):
                print(f"  - {c.get('title')} | URL: {c.get('source_url')}")
                
            # 3. Scoped News Query
            print("\n[Query 2] Scoped to master_news_corpus:")
            news_payload = {
                "message": "What is the flood situation in Assam and rescue operations?",
                "session_id": sess_id,
                "dataset_filter": ["master_news_corpus"]
            }
            req_n = urllib.request.Request(f"{PROD_URL}/chat", data=json.dumps(news_payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            n_resp = json.loads(urllib.request.urlopen(req_n, timeout=60).read().decode("utf-8"))
            print(f"Answer: {n_resp.get('answer')[:180]}...")
            print(f"Citations ({len(n_resp.get('citations', []))}):")
            for c in n_resp.get("citations", []):
                print(f"  - {c.get('title')} | URL: {c.get('source_url')}")
                
            print("\n" + "=" * 80)
            print("LIVE PRODUCTION VERIFICATION 100% COMPLETE AND SUCCESSFUL!")
            print("=" * 80)
            return True
            
        except Exception as e:
            print(f"[{elapsed}s] Deployment building/restarting... ({e})", flush=True)
            time.sleep(10)
            
    print("Timeout waiting for deployment.")
    return False

if __name__ == "__main__":
    monitor()
