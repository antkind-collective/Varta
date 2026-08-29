import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import time
import sqlite3
import numpy as np
import faiss
from src.embedding_providers import get_embedding_provider

def rebuild():
    print("=" * 80)
    print("REBUILDING FAISS INDEX TO 1-TO-1 SYNCHRONIZE WITH SQLITE")
    print("=" * 80)
    
    conn = sqlite3.connect("data/vector_db/metadata.sqlite")
    cursor = conn.cursor()
    cursor.execute("SELECT vector_id, content, title FROM chunk_metadata ORDER BY vector_id ASC")
    rows = cursor.fetchall()
    total_records = len(rows)
    max_vid = max(r[0] for r in rows)
    total_vectors = max_vid + 1
    print(f"Total records in SQLite: {total_records}, Max vector ID: {max_vid} -> Total vectors needed: {total_vectors}")
    
    emb_provider = get_embedding_provider()
    dim = emb_provider.get_dimension()
    print(f"Embedding dimension: {dim}")
    
    # Pre-allocate dense matrix for all vector IDs
    embeddings_matrix = np.zeros((total_vectors, dim), dtype=np.float32)
    
    batch_size = 512
    t0 = time.time()
    for i in range(0, total_records, batch_size):
        batch = rows[i:i + batch_size]
        texts = [(r[2] + " " + r[1]).strip() if r[2] else r[1] for r in batch]
        vids = [r[0] for r in batch]
        
        batch_embs = emb_provider.encode(texts)
        for vid, emb in zip(vids, batch_embs):
            embeddings_matrix[vid] = np.array(emb, dtype=np.float32)
            
        elapsed = time.time() - t0
        processed = min(i + batch_size, total_records)
        speed = processed / elapsed if elapsed > 0 else 0
        print(f"Processed {processed}/{total_records} ({processed/total_records*100:.1f}%) - {speed:.1f} chunks/sec", flush=True)
        
    print("Building FAISS IndexFlatIP...")
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings_matrix)
    print(f"FAISS index built with {index.ntotal} vectors.")
    
    faiss_out = "data/vector_db/faiss_index.bin"
    faiss.write_index(index, faiss_out)
    print(f"Saved synchronized FAISS index to {faiss_out}.")
    print("Rebuild complete!")

if __name__ == "__main__":
    rebuild()
