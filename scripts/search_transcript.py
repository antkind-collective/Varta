import json
from pathlib import Path

def search():
    log_path = Path(r"C:\Users\binda\.gemini\antigravity-ide\brain\418f1c44-fc63-4f52-9357-b60f3238213f\.system_generated\logs\transcript.jsonl")
    if not log_path.exists():
        print("Transcript not found")
        return
        
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f):
            try:
                obj = json.loads(line)
                content = str(obj.get("content", ""))
                thinking = str(obj.get("thinking", ""))
                text = content + " " + thinking
                for match in ["50,", "509", "504", "501", "50 "]:
                    if match in text:
                        step = obj.get("step_index", idx)
                        source = obj.get("source", "")
                        print(f"--- Step {step} ({source}) ---")
                        # print first 200 chars around match
                        mpos = text.find(match)
                        start = max(0, mpos - 100)
                        end = min(len(text), mpos + 150)
                        print(text[start:end].strip())
                        print()
                        break
            except Exception:
                pass

if __name__ == "__main__":
    search()
