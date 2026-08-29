import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from api.app import app

def test_app():
    client = TestClient(app)
    
    # 1. Health check
    resp = client.get("/health")
    assert resp.status_code == 200, f"Health check failed: {resp.text}"
    print("[1] Local /health check:", resp.json())
    
    # 2. Session creation
    resp_s = client.post("/session")
    assert resp_s.status_code == 201, f"Session create failed: {resp_s.text}"
    session_id = resp_s.json()["session_id"]
    print("[2] Local /session create:", session_id)
    
    # 3. Chat turn
    resp_c = client.post("/chat", json={"message": "What is the flood situation in Assam?", "session_id": session_id})
    assert resp_c.status_code == 200, f"Chat failed: {resp_c.text}"
    print("[3] Local /chat response plan:", resp_c.json().get("plan_type"))
    print("Local App Test Succeeded 100%!")

if __name__ == "__main__":
    test_app()
