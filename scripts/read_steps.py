import json
from pathlib import Path

def read_steps():
    log_path = Path(r"C:\Users\binda\.gemini\antigravity-ide\brain\418f1c44-fc63-4f52-9357-b60f3238213f\.system_generated\logs\transcript_full.jsonl")
    if not log_path.exists():
        log_path = Path(r"C:\Users\binda\.gemini\antigravity-ide\brain\418f1c44-fc63-4f52-9357-b60f3238213f\.system_generated\logs\transcript.jsonl")

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                obj = json.loads(line)
                step = obj.get("step_index")
                if step in [2084, 2090, 2096, 2121, 2123, 2127, 2131]:
                    print(f"=== STEP {step} ===")
                    print(obj.get("content"))
                    print()
            except Exception:
                pass

if __name__ == "__main__":
    read_steps()
