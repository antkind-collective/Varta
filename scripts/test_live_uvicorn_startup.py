import subprocess
import time
import urllib.request
import json
import sys
import os

def test_uvicorn_startup():
    print("=" * 80)
    print("STARTING LIVE LOCAL UVICORN SERVER (EXACT RAILWAY STARTUP SIMULATION)")
    print("=" * 80)
    
    port = 8008
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["VARTA_PORT"] = str(port)
    env["VARTA_ENV"] = "production"
    
    cmd = [sys.executable, "-m", "uvicorn", "api.app:app", "--host", "127.0.0.1", "--port", str(port), "--workers", "1"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    
    try:
        # Poll server until live
        start_time = time.time()
        live = False
        health_resp = None
        
        while time.time() - start_time < 30:
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                print("FATAL: Uvicorn exited prematurely with code:", proc.returncode)
                print("STDOUT:", stdout)
                print("STDERR:", stderr)
                sys.exit(1)
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        health_resp = json.loads(resp.read().decode("utf-8"))
                        live = True
                        break
            except Exception:
                time.sleep(1)
                
        if not live:
            stdout, stderr = proc.communicate(timeout=2)
            print("Server failed to respond within 30s.")
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            sys.exit(1)
            
        print("[SUCCESS] Local Uvicorn server started and bound to port", port)
        print("[1] /health response:", health_resp)
        
        # Test /datasets/list
        req_d = urllib.request.Request(f"http://127.0.0.1:{port}/datasets/list")
        with urllib.request.urlopen(req_d, timeout=5) as resp:
            ds_resp = json.loads(resp.read().decode("utf-8"))
            print("[2] /datasets/list response:", ds_resp)
            assert ds_resp.get("total_datasets", 0) >= 2, "Expected at least 2 datasets"
            
        # Test /session
        req_s = urllib.request.Request(f"http://127.0.0.1:{port}/session", data=b"", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_s, timeout=5) as resp:
            sess_resp = json.loads(resp.read().decode("utf-8"))
            print("[3] /session response:", sess_resp)
            sess_id = sess_resp["session_id"]
            
        print("\n" + "=" * 80)
        print("ALL UVICORN LOCAL SERVER STARTUP & ENDPOINT CHECKS PASSED 100%!")
        print("=" * 80)
        
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    test_uvicorn_startup()
