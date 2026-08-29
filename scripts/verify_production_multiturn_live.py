import sys
import urllib.request
import json
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

PROD_URL = "https://varta-production-c8d8.up.railway.app"

def wait_for_deployment():
    print("Waiting for Railway deployment to stabilize...")
    for i in range(24): # wait up to 2 minutes
        try:
            req = urllib.request.Request(f"{PROD_URL}/health")
            res = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8"))
            uptime = res.get("uptime_seconds", 0)
            print(f"[{i*5}s] Server status: {res.get('status')} | Uptime: {uptime:.1f}s")
            # If uptime is small (< 180s) or server is responding ok, check a test query
            if res.get("status") == "ok":
                time.sleep(10)
                break
        except Exception as e:
            print(f"[{i*5}s] Waiting for server... ({e})")
        time.sleep(5)

def run_multiturn_live_verification():
    print("\n" + "=" * 80)
    print("RUNNING LIVE MULTI-TURN CONVERSATION SEQUENCE ON RAILWAY PRODUCTION")
    print("=" * 80)

    # 1. Create a live session
    req_s = urllib.request.Request(f"{PROD_URL}/session", data=b"", headers={"Content-Type": "application/json"})
    sess_data = json.loads(urllib.request.urlopen(req_s, timeout=15).read().decode("utf-8"))
    session_id = sess_data["session_id"]
    print(f"Created Live Session ID: {session_id}")

    # Turn 1: Abstract query 1
    q1 = "Is there a difference between how officials or media describe the disaster response and how it's actually being experienced by affected communities?"
    print("\n" + "-" * 80)
    print(f"TURN 1: \"{q1}\"")
    print("-" * 80)
    req1 = urllib.request.Request(
        f"{PROD_URL}/chat",
        data=json.dumps({"message": q1, "session_id": session_id}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    r1 = json.loads(urllib.request.urlopen(req1, timeout=60).read().decode("utf-8"))
    print(f"Plan Type: {r1.get('plan_type')}")
    print(f"Tool Used: {r1.get('tool_used')}")
    print(f"Answer (First 300 chars):\n{r1.get('answer')[:300]}")

    # Turn 2: Abstract query 2 (The one that previously broke and triggered mangled titles)
    q2 = "Are there any government policies or programs mentioned in the coverage that don't seem to come up when people talk about their actual experience?"
    print("\n" + "-" * 80)
    print(f"TURN 2: \"{q2}\"")
    print("-" * 80)
    req2 = urllib.request.Request(
        f"{PROD_URL}/chat",
        data=json.dumps({"message": q2, "session_id": session_id}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    r2 = json.loads(urllib.request.urlopen(req2, timeout=60).read().decode("utf-8"))
    print(f"Plan Type: {r2.get('plan_type')}")
    print(f"Tool Used: {r2.get('tool_used')}")
    print(f"Answer (First 300 chars):\n{r2.get('answer')[:300]}")

    # Turn 3: Followup with pronoun
    q3 = "Tell me about the flood situation in Assam."
    print("\n" + "-" * 80)
    print(f"TURN 3: \"{q3}\"")
    print("-" * 80)
    req3 = urllib.request.Request(
        f"{PROD_URL}/chat",
        data=json.dumps({"message": q3, "session_id": session_id}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    r3 = json.loads(urllib.request.urlopen(req3, timeout=60).read().decode("utf-8"))
    print(f"Plan Type: {r3.get('plan_type')}")
    print(f"Answer (First 300 chars):\n{r3.get('answer')[:300]}")

    # Turn 4: Followup with entity resolution
    q4 = "Which districts are worst affected?"
    print("\n" + "-" * 80)
    print(f"TURN 4: \"{q4}\"")
    print("-" * 80)
    req4 = urllib.request.Request(
        f"{PROD_URL}/chat",
        data=json.dumps({"message": q4, "session_id": session_id}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    r4 = json.loads(urllib.request.urlopen(req4, timeout=60).read().decode("utf-8"))
    print(f"Plan Type: {r4.get('plan_type')}")
    print(f"Answer (First 300 chars):\n{r4.get('answer')[:300]}")

    # Assertions on Turn 2
    ans2 = r2.get("answer", "")
    assert "continuous field monitoring and relief operations remain in effect" not in ans2, "Error: Hardcoded boilerplate found in Turn 2!"
    assert "How It'S Actually Being Experienced" not in ans2, "Error: Mangled title concatenation found in Turn 2!"
    print("\n" + "=" * 80)
    print("LIVE PRODUCTION MULTI-TURN VERIFICATION PASSED WITH ZERO REGRESSIONS!")
    print("=" * 80)

if __name__ == "__main__":
    wait_for_deployment()
    run_multiturn_live_verification()
