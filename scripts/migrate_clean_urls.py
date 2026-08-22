import sqlite3
import re
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
db_path = project_root / "data" / "vector_db" / "metadata.sqlite"

print(f"Connecting to database: {db_path}")
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

# Fetch all records with HTTP URLs
cur.execute("SELECT vector_id, parent_doc_id, post_id FROM chunk_metadata WHERE parent_doc_id LIKE 'http%' OR post_id LIKE 'http%'")
rows = cur.fetchall()
print(f"Found {len(rows):,} chunk records with HTTP URLs in database.")

updates = []
for vector_id, parent_doc_id, post_id in rows:
    new_parent_id = re.sub(r'\.\d+$', '', parent_doc_id) if parent_doc_id and parent_doc_id.startswith("http") else parent_doc_id
    new_post_id = re.sub(r'\.\d+$', '', post_id) if post_id and post_id.startswith("http") else post_id
    
    if new_parent_id != parent_doc_id or new_post_id != post_id:
        updates.append((new_parent_id, new_post_id, vector_id))

print(f"Found {len(updates):,} records requiring .<num> suffix removal.")

cur.executemany("UPDATE chunk_metadata SET parent_doc_id = ?, post_id = ? WHERE vector_id = ?", updates)
conn.commit()
print("Database commit successful.")

# Verification
cur.execute("SELECT COUNT(*) FROM chunk_metadata WHERE parent_doc_id LIKE 'http%' AND parent_doc_id GLOB '*.[0-9]'")
corrupt_count = cur.fetchone()[0]
print(f"Post-migration check: Records with trailing .<digit> suffix: {corrupt_count}")

conn.close()
