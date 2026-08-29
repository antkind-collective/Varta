import sqlite3

conn = sqlite3.connect("data/vector_db/metadata.sqlite")
cursor = conn.cursor()

print("--- Sample Rows (parent_doc_id, post_id, source_type, source_url) ---")
cursor.execute("SELECT parent_doc_id, post_id, source_type, source_url FROM chunk_metadata LIMIT 10;")
for r in cursor.fetchall():
    print(r)

print("\n--- Parent Doc ID Patterns ---")
cursor.execute("SELECT CASE WHEN parent_doc_id LIKE 'mo-%' THEN 'Meltwater (mo-*)' WHEN parent_doc_id LIKE 'http%' THEN 'URL-based (http*)' ELSE 'Other' END as pfx_type, count(*) FROM chunk_metadata GROUP BY pfx_type;")
for r in cursor.fetchall():
    print(r)

print("\n--- Reddit vs Non-Reddit in source_url / title / content ---")
cursor.execute("SELECT count(*) FROM chunk_metadata WHERE source_url LIKE '%reddit.com%' OR parent_doc_id LIKE '%reddit.com%';")
reddit_cnt = cursor.fetchone()[0]
print(f"Reddit-origin chunks: {reddit_cnt}")

cursor.execute("SELECT count(*) FROM chunk_metadata WHERE source_url NOT LIKE '%reddit.com%' AND (parent_doc_id NOT LIKE '%reddit.com%' OR parent_doc_id IS NULL);")
non_reddit_cnt = cursor.fetchone()[0]
print(f"Non-Reddit chunks: {non_reddit_cnt}")

conn.close()
