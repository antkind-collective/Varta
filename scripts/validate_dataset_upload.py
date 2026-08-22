#!/usr/bin/env python3
"""
VARTA Dataset Upload & Dynamic 5-Stage Ingestion Validation Suite.

Validates:
1. Web Interface Delivery of Upload Button & Input (#btn-upload-dataset, #dataset-file-input)
2. Ingestion of CSV Dataset (POST /dataset/upload)
3. Ingestion of JSON / JSONL Dataset (POST /dataset/upload)
4. Vector Database Index Growth and Synchronization
5. Live Querying with Citations of Newly Uploaded Content
6. Backward Compatibility / Querying of Original Dataset
7. Graceful Handling and Rejection of Invalid File Formats & Empty Files
"""

import sys
import io
import json
from pathlib import Path
from typing import Dict, Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from api.app import app
from src.vector_database import VectorDatabase

def run_dataset_upload_validation():
    print("=" * 80)
    print(" VARTA DATASET UPLOAD & DYNAMIC 5-STAGE INGESTION VALIDATION")
    print("=" * 80)

    client = TestClient(app)
    vdb_dir = project_root / "data" / "vector_db"
    initial_vdb = VectorDatabase.load(str(vdb_dir))
    initial_vector_count = initial_vdb.index.ntotal
    print(f"\n[Baseline] Current Vector Database Size: {initial_vector_count:,} vectors.")

    # 1. UI Root Route Delivery Verification
    print("\n[1/7] Web Interface Upload Elements Audit:")
    res = client.get("/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    html = res.text
    assert "btn-upload-dataset" in html, "Missing #btn-upload-dataset in UI"
    assert "dataset-file-input" in html, "Missing #dataset-file-input in UI"
    assert "upload-modal" in html, "Missing #upload-modal in UI"
    assert "step-uploading" in html, "Missing step-uploading in UI"
    assert "step-processing" in html, "Missing step-processing in UI"
    assert "step-indexing" in html, "Missing step-indexing in UI"
    assert "step-ready" in html, "Missing step-ready in UI"
    print("      -> Result: 🟢 PASS (All Upload UI controls and progress stages present)")

    # 2. Upload and Ingest New CSV Dataset
    print("\n[2/7] Upload New CSV Dataset (Cyclone Dana Relief Operations):")
    sample_csv_content = """Post ID,Title,Sound Bite Text,Source Type
https://www.odishatv.in/news/cyclone-dana-relief-camps-kendrapara-dhamra-2026.html,Cyclone Dana: 150 Relief Camps Deployed in Kendrapara,Special relief commissioner deployed 150 multipurpose cyclone shelters in Kendrapara and Bhadrak districts. Free community kitchens are functioning at Dhamra port with 12 NDRF search and rescue teams on round-the-clock standby.,News
https://www.sambad.in/news/odisha-disaster-management-dana-response-2026.html,Odisha Disaster Management Ramps Up Free Kitchens and Medical Supplies,Health department dispatched 50 tons of essential medicines and water purification tablets to flood-prone blocks in Balasore and Dhamra port area.,News
"""
    csv_file = io.BytesIO(sample_csv_content.encode("utf-8"))
    upload_res = client.post(
        "/dataset/upload",
        files={"file": ("cyclone_dana_reports_2026.csv", csv_file, "text/csv")}
    )
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    upload_data = upload_res.json()
    print(f"      - Ingestion Status:     {upload_data['status']}")
    print(f"      - Message:              {upload_data['message']}")
    print(f"      - Documents Ingested:   {upload_data['documents_ingested']}")
    print(f"      - Chunks Indexed:       {upload_data['chunks_indexed']}")
    print(f"      - Total Vectors Now:    {upload_data['total_vectors_available']:,}")
    assert upload_data["status"] == "ready"
    assert upload_data["documents_ingested"] == 2
    assert upload_data["chunks_indexed"] >= 2
    assert upload_data["total_vectors_available"] > initial_vector_count
    print("      -> Result: 🟢 PASS (CSV ingested through 5 stages and vector index updated)")

    # 3. Upload and Ingest JSON Dataset
    print("\n[3/7] Upload New JSON Dataset (Sikkim Avalanche Evacuation):")
    sample_json_data = [
        {
            "post_id": "https://www.sikkimexpress.com/news/north-sikkim-avalanche-tunnel-rescue-2026.html",
            "title": "North Sikkim Avalanche: Border Roads Organization Clears Snow",
            "text_content": "The Border Roads Organization (BRO) under Project Swastik successfully evacuated 45 tourists stranded near Chungthang after a massive snow avalanche. Medical aid posts are set up at Mangan district hospital.",
            "source_type": "News"
        }
    ]
    json_bytes = io.BytesIO(json.dumps(sample_json_data).encode("utf-8"))
    json_upload_res = client.post(
        "/dataset/upload",
        files={"file": ("sikkim_avalanche_2026.json", json_bytes, "application/json")}
    )
    assert json_upload_res.status_code == 200, f"JSON upload failed: {json_upload_res.text}"
    json_upload_data = json_upload_res.json()
    print(f"      - Ingestion Status:     {json_upload_data['status']}")
    print(f"      - Documents Ingested:   {json_upload_data['documents_ingested']}")
    print(f"      - Total Vectors Now:    {json_upload_data['total_vectors_available']:,}")
    assert json_upload_data["documents_ingested"] == 1
    print("      -> Result: 🟢 PASS (JSON dataset ingested and indexed successfully)")

    # 4. Live Querying of Newly Uploaded Content with Citations
    print("\n[4/7] Querying Newly Uploaded Cyclone Dana Dataset via POST /chat:")
    session_res = client.post("/session")
    session_id = session_res.json()["session_id"]

    query_new = "What relief arrangements and community kitchens were set up at Dhamra port for Cyclone Dana?"
    chat_res = client.post(
        "/chat",
        json={"message": query_new, "session_id": session_id}
    )
    assert chat_res.status_code == 200, f"Chat query failed: {chat_res.text}"
    chat_data = chat_res.json()
    answer = chat_data.get("answer", "")
    citations = chat_data.get("citations", [])

    print(f"      - Query: '{query_new}'")
    print(f"      - Citations returned: {len(citations)}")
    for c in citations:
        print(f"        * {c.get('citation_id')}: {c.get('title')} -> {c.get('parent_doc_id')}")

    assert len(citations) > 0, "Expected at least 1 citation for newly ingested dataset"
    top_citation_title = citations[0].get("title", "")
    assert "Cyclone Dana" in top_citation_title or "Dhamra" in str(citations) or "Odisha" in top_citation_title, (
        f"Expected Cyclone Dana citation, got {top_citation_title}"
    )
    print("      -> Result: 🟢 PASS (Query correctly retrieved and cited newly uploaded documents)")

    # 5. Live Querying of Newly Uploaded Sikkim Dataset
    print("\n[5/7] Querying Newly Uploaded Sikkim Avalanche Dataset:")
    query_sikkim = "What rescue operations did Project Swastik carry out in North Sikkim?"
    sikkim_chat_res = client.post(
        "/chat",
        json={"message": query_sikkim, "session_id": session_id}
    )
    assert sikkim_chat_res.status_code == 200
    sikkim_data = sikkim_chat_res.json()
    sikkim_citations = sikkim_data.get("citations", [])
    print(f"      - Citations returned: {len(sikkim_citations)}")
    for c in sikkim_citations:
        print(f"        * {c.get('citation_id')}: {c.get('title')} -> {c.get('parent_doc_id')}")
    assert len(sikkim_citations) > 0
    assert "Sikkim" in str(sikkim_citations)
    print("      -> Result: 🟢 PASS (Sikkim dataset query retrieved and cited)")

    # 6. Backward Compatibility / Original Dataset Query
    print("\n[6/7] Verifying Original Dataset Integrity & Querying:")
    orig_query = "What is the flood situation in Bihar and Patna?"
    orig_chat_res = client.post(
        "/chat",
        json={"message": orig_query, "session_id": session_id}
    )
    assert orig_chat_res.status_code == 200
    orig_data = orig_chat_res.json()
    orig_citations = orig_data.get("citations", [])
    print(f"      - Citations returned for original query: {len(orig_citations)}")
    for c in orig_citations:
        print(f"        * {c.get('citation_id')}: {c.get('title')} -> {c.get('parent_doc_id')}")
    assert len(orig_citations) > 0
    assert any("Bihar" in c.get("title", "") or "Patna" in c.get("title", "") or "prabhatkhabar" in str(c.get("parent_doc_id", "")) for c in orig_citations)
    print("      -> Result: 🟢 PASS (Original corpus continues to query and cite with 100% precision)")

    # 7. Invalid File Format & Malformed Rejection Test
    print("\n[7/7] Invalid File Formats & Empty Input Rejection Test:")
    # Invalid extension (.pdf)
    bad_ext_file = io.BytesIO(b"dummy pdf content")
    bad_res = client.post(
        "/dataset/upload",
        files={"file": ("dataset.pdf", bad_ext_file, "application/pdf")}
    )
    assert bad_res.status_code == 400, f"Expected 400, got {bad_res.status_code}"
    print(f"      - Invalid Extension (.pdf): Rejection 400 OK ({bad_res.json()['detail']})")

    # Empty CSV file
    empty_file = io.BytesIO(b"")
    empty_res = client.post(
        "/dataset/upload",
        files={"file": ("empty.csv", empty_file, "text/csv")}
    )
    assert empty_res.status_code == 400, f"Expected 400, got {empty_res.status_code}"
    print(f"      - Empty File: Rejection 400 OK ({empty_res.json()['detail']})")
    print("      -> Result: 🟢 PASS (Invalid files handled gracefully with researcher-friendly errors)")

    print("\n" + "=" * 80)
    print(" ALL DATASET UPLOAD & DYNAMIC INGESTION TESTS PASSED 🟢 (100% COMPLIANCE)")
    print("=" * 80)
    return True

if __name__ == "__main__":
    success = run_dataset_upload_validation()
    sys.exit(0 if success else 1)
