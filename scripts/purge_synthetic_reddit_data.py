import os
import sqlite3
import json
import faiss
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "vector_db" / "metadata.sqlite"
FAISS_PATH = PROJECT_ROOT / "data" / "vector_db" / "faiss_index.bin"
MANIFEST_PATH = PROJECT_ROOT / "data" / "vector_db" / "db_manifest.json"
CSV_PATH = PROJECT_ROOT / "data" / "uploads" / "sagar_reddit_dataset.csv"

def purge_synthetic_reddit_dataset():
    print("=" * 80)
    print("PURGING SYNTHETIC SAGAR REDDIT DATASET")
    print("=" * 80)

    # 1. Connect to SQLite and check rows
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    reddit_rows = cur.execute("SELECT vector_id, chunk_id, title, source_dataset FROM chunk_metadata WHERE source_dataset = 'sagar_reddit_dataset'").fetchall()
    print(f"\n[1/4] Found {len(reddit_rows)} rows in chunk_metadata under 'sagar_reddit_dataset':")
    for r in reddit_rows:
        print(f"  - Vector ID {r[0]}: Chunk {r[1]} - \"{r[2]}\"")

    # 2. Delete rows from SQLite
    cur.execute("DELETE FROM chunk_metadata WHERE source_dataset = 'sagar_reddit_dataset'")
    conn.commit()
    print(f"\n[2/4] Successfully deleted {len(reddit_rows)} rows from metadata.sqlite.")

    # 3. Clean / Re-sync FAISS index if vectors were added
    if FAISS_PATH.exists():
        index = faiss.read_index(str(FAISS_PATH))
        total_vectors = index.ntotal
        print(f"\n[3/4] Current FAISS index vector count: {total_vectors}")

        # Check total remaining rows in SQLite
        remaining_count = cur.execute("SELECT COUNT(*) FROM chunk_metadata").fetchone()[0]
        print(f"      Remaining SQLite chunk_metadata count: {remaining_count}")

        # If FAISS index had extra vectors appended at the end (e.g. 39164 + 8 = 39172), rebuild or reconstruct the clean index
        if total_vectors > remaining_count:
            print(f"      Re-slicing FAISS index to exact {remaining_count} vectors...")
            all_vectors = index.reconstruct_n(0, remaining_count)
            dim = index.d
            new_index = faiss.IndexFlatIP(dim)
            new_index.add(all_vectors)
            faiss.write_index(new_index, str(FAISS_PATH))
            print(f"      Clean FAISS index saved with {new_index.ntotal} vectors.")

    conn.close()

    # Update manifest
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["total_vectors"] = remaining_count
        manifest["total_chunks"] = remaining_count
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"      Updated db_manifest.json (total_vectors: {remaining_count}).")

    # 4. Delete the CSV file
    if CSV_PATH.exists():
        os.remove(CSV_PATH)
        print(f"\n[4/4] Successfully deleted synthetic CSV: {CSV_PATH}")
    else:
        print(f"\n[4/4] Synthetic CSV not found: {CSV_PATH}")

    # 5. Final Verification
    conn_verify = sqlite3.connect(DB_PATH)
    cur_v = conn_verify.cursor()
    remaining_reddit = cur_v.execute("SELECT COUNT(*) FROM chunk_metadata WHERE source_dataset = 'sagar_reddit_dataset'").fetchone()[0]
    total_chunks = cur_v.execute("SELECT COUNT(*) FROM chunk_metadata").fetchone()[0]
    dataset_breakdown = cur_v.execute("SELECT source_dataset, COUNT(*) FROM chunk_metadata GROUP BY source_dataset").fetchall()
    conn_verify.close()

    print("\n" + "=" * 80)
    print("VERIFICATION AFTER PURGE:")
    print(f"  - Rows under 'sagar_reddit_dataset': {remaining_reddit}")
    print(f"  - Total chunks in DB: {total_chunks}")
    print(f"  - Dataset breakdown: {dataset_breakdown}")
    print(f"  - CSV file exists: {CSV_PATH.exists()}")
    print("=" * 80)

    assert remaining_reddit == 0, "Error: sagar_reddit_dataset rows still exist in DB!"
    assert not CSV_PATH.exists(), "Error: sagar_reddit_dataset.csv was not deleted!"

if __name__ == "__main__":
    purge_synthetic_reddit_dataset()
