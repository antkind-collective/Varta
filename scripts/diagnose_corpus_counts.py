import sqlite3
import json
from pathlib import Path

def diagnose():
    print("=" * 80)
    print("DIAGNOSING CORPUS COUNTS & DATABASE HISTORY")
    print("=" * 80)
    
    # 1. Inspect metadata.sqlite
    sqlite_path = Path("data/vector_db/metadata.sqlite")
    if sqlite_path.exists():
        conn = sqlite3.connect(str(sqlite_path))
        cursor = conn.cursor()
        print(f"\n[1] Current SQLite metadata store: {sqlite_path}")
        try:
            groups = cursor.execute("SELECT source_dataset, COUNT(*) FROM chunk_metadata GROUP BY source_dataset").fetchall()
            print("  source_dataset counts in chunk_metadata:")
            for g in groups:
                print(f"    - {g[0]}: {g[1]:,} rows")
            total = cursor.execute("SELECT COUNT(*) FROM chunk_metadata").fetchone()[0]
            print(f"  Total rows: {total:,}")
            min_v, max_v = cursor.execute("SELECT MIN(vector_id), MAX(vector_id) FROM chunk_metadata").fetchone()
            print(f"  Min vector_id: {min_v}, Max vector_id: {max_v}")
        except Exception as e:
            print(f"  Error querying chunk_metadata: {e}")
            
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"  All tables: {[t[0] for t in tables]}")
        for t in tables:
            tname = t[0]
            if tname != "chunk_metadata":
                cnt = cursor.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
                print(f"    Table {tname}: {cnt:,} rows")
        conn.close()
        
    # 2. Check other db files
    varta_db = Path("data/vector_db/varta_metadata.db")
    if varta_db.exists():
        print(f"\n[2] Found varta_metadata.db: {varta_db} ({varta_db.stat().st_size / 1024 / 1024:.2f} MB)")
        try:
            conn2 = sqlite3.connect(str(varta_db))
            cursor2 = conn2.cursor()
            tables2 = cursor2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            print(f"  Tables in varta_metadata.db: {[t[0] for t in tables2]}")
            for t in tables2:
                tname = t[0]
                cnt = cursor2.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
                print(f"    Table {tname}: {cnt:,} rows")
                if "chunk" in tname:
                    groups = cursor2.execute(f"SELECT source_dataset, COUNT(*) FROM {tname} GROUP BY source_dataset").fetchall()
                    print(f"    source_dataset counts in {tname}: {groups}")
            conn2.close()
        except Exception as e:
            print(f"  Error reading varta_metadata.db: {e}")
            
    # 3. Check data/embeddings and data/processed
    print("\n[3] Checking data/ directory files:")
    for p in sorted(Path("data").rglob("*.*")):
        if p.suffix in [".sqlite", ".db", ".json", ".npy", ".bin", ".csv", ".parquet"]:
            size_mb = p.stat().st_size / (1024 * 1024)
            print(f"  - {p} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    diagnose()
