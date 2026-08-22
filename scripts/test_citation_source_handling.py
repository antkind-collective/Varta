#!/usr/bin/env python3
"""
Test Suite for Citation / Source Handling & Meta-Query Routing in VARTA.

Validates:
1. Document containing a genuine URL preserves and returns source_url.
2. Document containing only a Doc ID returns source_url as None and displays Doc ID (never invented).
3. Meta questions about VARTA & citations (e.g. 'Why are you not giving me URLs for the references?')
   route to system_info without triggering RAG document retrieval.
4. Preprocessing & ingestion of datasets with separate id and url columns.
"""

import sys
import os
import re
import json
import pandas as pd
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.data_cleaner import DataCleaner
from src.metadata_processor import MetadataProcessor
from src.metadata_formatter import MetadataFormatter
from src.document_builder import DocumentBuilder
from src.chunk_builder import ChunkBuilder
from src.metadata_store import MetadataStore
from src.vector_database import VectorDatabase
from src.semantic_retriever import SemanticRetriever
from src.rag_orchestrator import RAGOrchestrator
from src.llm_adapter import MockLLMAdapter
from src.agent_planner import AgentPlanner
from src.assistant_controller import AssistantController

def test_preprocessing_and_standardization():
    print("\n[TEST 1] Preprocessing & Standardization with URLs and Doc IDs...")
    
    # Create sample DataFrame with mixed cases:
    # Row 1: Has explicit source_url and separate id
    # Row 2: Has only post_id as an alphanumeric ID (no URL)
    # Row 3: Has post_id as a URL
    data = {
        "id": ["doc_custom_001", "mo-ln-99887766", "https://news.example.com/article3.html"],
        "title": ["Rescue Op in Zone A", "Relief Shelter Setup in Zone B", "Helicopter Evacuation in Zone C"],
        "content": ["Troops rescued 200 people from Zone A.", "Shelters established in Zone B.", "Helicopters air-dropped aid in Zone C."],
        "url": ["https://news.example.com/article1.html", None, None],
        "source": ["News", "Government", "News"]
    }
    df = pd.DataFrame(data)

    config = {
        "column_rename_map": {},
        "columns_to_drop": [],
        "core_payload_columns": ["title", "content"],
        "identifier_column": "post_id"
    }

    cleaner = DataCleaner(config)
    df_clean, struct_stats = cleaner.clean_structure_and_columns(df)
    df_valid, filter_stats = cleaner.filter_and_fill_identifiers(df_clean)

    assert "source_url" in df_valid.columns, "Expected source_url column to be preserved"
    assert "post_id" in df_valid.columns, "Expected post_id column to be preserved"

    meta_proc = MetadataProcessor()
    df_meta, _ = meta_proc.process_metadata(df_valid)

    doc_builder = DocumentBuilder()
    docs = [doc_builder.build_document(row, idx) for idx, (_, row) in enumerate(df_meta.iterrows())]

    # Row 1 check
    assert docs[0]["doc_id"] == "doc_custom_001"
    assert docs[0]["metadata"]["source_url"] == "https://news.example.com/article1.html"

    # Row 2 check (no URL)
    assert docs[0]["doc_id"] == "doc_custom_001"
    assert docs[1]["doc_id"] == "mo-ln-99887766"
    assert docs[1]["metadata"]["source_url"] is None, "Expected source_url to be None for non-URL document"

    # Row 3 check (URL as post_id)
    assert docs[2]["metadata"]["source_url"] == "https://news.example.com/article3.html"

    print("  -> Passed: URL and Doc ID metadata correctly preserved across preprocessing & standardization.")

def test_sqlite_metadata_storage():
    print("\n[TEST 2] SQLite Metadata Storage & Retrieval for URLs vs Doc IDs...")
    
    test_db_path = project_root / "data" / "vector_db" / "test_metadata.sqlite"
    if test_db_path.exists():
        os.remove(test_db_path)

    store = MetadataStore(str(test_db_path))

    chunks = [
        {
            "chunk_id": "chunk_with_url#000",
            "parent_doc_id": "doc_001",
            "chunk_index": 0,
            "total_chunks": 1,
            "title": "Disaster Relief URL Doc",
            "content": "Emergency teams deployed with food packets.",
            "embedding_text": "Disaster Relief URL Doc Emergency teams deployed",
            "char_count": 45,
            "word_count": 6,
            "metadata": {
                "post_id": "doc_001",
                "source_url": "https://www.thehindu.com/news/kerala-flood-relief.html",
                "source_type": "News"
            }
        },
        {
            "chunk_id": "chunk_doc_id_only#000",
            "parent_doc_id": "mo-ln-12345678",
            "chunk_index": 0,
            "total_chunks": 1,
            "title": "Disaster Relief Doc ID Only",
            "content": "Local administration issued flood alert.",
            "embedding_text": "Disaster Relief Doc ID Only Local administration issued flood alert",
            "char_count": 40,
            "word_count": 5,
            "metadata": {
                "post_id": "mo-ln-12345678",
                "source_url": None,
                "source_type": "Government"
            }
        }
    ]

    store.populate_from_chunks(chunks)
    retrieved = store.get_metadata_by_vector_ids([0, 1])

    # Check chunk 0
    assert retrieved[0]["metadata"]["source_url"] == "https://www.thehindu.com/news/kerala-flood-relief.html"
    assert retrieved[0]["parent_doc_id"] == "doc_001"

    # Check chunk 1
    assert retrieved[1]["metadata"]["source_url"] is None, "Expected source_url to be None"
    assert retrieved[1]["parent_doc_id"] == "mo-ln-12345678"

    if test_db_path.exists():
        os.remove(test_db_path)

    print("  -> Passed: SQLite correctly stores and retrieves source_url and Doc ID distinctly.")

def test_rag_pipeline_citations():
    print("\n[TEST 3] Live RAG Pipeline Citation Generation for URL vs Non-URL...")

    vdb = VectorDatabase.load(str(project_root / "data" / "vector_db"))
    retriever = SemanticRetriever(vector_db=vdb)
    mock_llm = MockLLMAdapter()
    orchestrator = RAGOrchestrator(retriever=retriever, llm_adapter=mock_llm)

    # 1. Query known to retrieve URL documents (Bihar flood)
    res_url = orchestrator.run_pipeline("What is the flood situation in Bihar?")
    citations_url = res_url.get("citations", [])
    assert len(citations_url) > 0, "Expected at least 1 citation"
    has_url = any(c.get("source_url") and c["source_url"].startswith("http") for c in citations_url)
    assert has_url, "Expected at least one citation with a valid source_url"
    for c in citations_url:
        assert "doc_id" in c, "Expected doc_id in citation"
        assert "source_url" in c, "Expected source_url in citation"
        if c["source_url"]:
            assert c["source_url"].startswith("http"), f"Invalid source_url: {c['source_url']}"
            assert not re.search(r'\.\d+$', c["source_url"]), f"Found scraper suffix: {c['source_url']}"

    print(f"  -> URL Query: Retrieved {len(citations_url)} citations. Sample source_url: {citations_url[0]['source_url']}")

    # 2. Query known to retrieve Non-URL documents (Rapti river in Gorakhpur)
    res_docid = orchestrator.run_pipeline("What is the condition of Rapti river in Gorakhpur?")
    citations_docid = res_docid.get("citations", [])
    assert len(citations_docid) > 0, "Expected at least 1 citation"
    
    non_url_found = False
    for c in citations_docid:
        if c.get("source_url") is None:
            non_url_found = True
            assert c.get("doc_id"), "Expected non-empty doc_id"
            assert not str(c.get("doc_id")).startswith("http"), "doc_id should be alphanumeric"

    assert non_url_found, "Expected at least one non-URL document citation"
    print(f"  -> Non-URL Query: Retrieved {len(citations_docid)} citations. Sample doc_id: {citations_docid[0]['doc_id']}, source_url: {citations_docid[0]['source_url']}")

def test_meta_question_routing():
    print("\n[TEST 4] Meta-Questions About VARTA & Citation Handling (Zero RAG Retrieval)...")

    vdb = VectorDatabase.load(str(project_root / "data" / "vector_db"))
    retriever = SemanticRetriever(vector_db=vdb)
    mock_llm = MockLLMAdapter()
    orchestrator = RAGOrchestrator(retriever=retriever, llm_adapter=mock_llm)
    controller = AssistantController(rag_orchestrator=orchestrator)

    meta_queries = [
        "Why are you not giving me URLs for the references?",
        "Why are there no URLs for the citations?",
        "Why do some citations show Doc ID instead of a link?",
        "Why are you only showing doc ids?",
        "How do citations work in VARTA?",
        "What is VARTA?",
        "What can you do?"
    ]

    for q in meta_queries:
        resp = controller.process_query(q)
        plan_type = resp.get("plan_type")
        tool_used = resp.get("tool_selected")
        citations = resp.get("citations", [])
        answer = resp.get("assistant_answer", "")

        print(f"  - Query: '{q}'")
        print(f"    Plan Type: {plan_type} | Tool Used: {tool_used} | Citations: {len(citations)}")
        print(f"    Answer snippet: {answer[:120]}...\n")

        assert plan_type == "system_info", f"Expected plan_type 'system_info' for '{q}', got '{plan_type}'"
        assert tool_used == "system_info", f"Expected tool 'system_info' for '{q}', got '{tool_used}'"
        assert len(citations) == 0, f"Expected 0 citations for meta query '{q}', got {len(citations)}"
        assert "Source URL" in answer or "VARTA" in answer or "Doc ID" in answer, "Expected explanatory answer"

    print("  -> Passed: All meta-questions routed to system_info without triggering RAG document retrieval.")

def run_all_tests():
    print("=" * 80)
    print(" VARTA CITATION & SOURCE HANDLING VERIFICATION SUITE")
    print("=" * 80)

    test_preprocessing_and_standardization()
    test_sqlite_metadata_storage()
    test_rag_pipeline_citations()
    test_meta_question_routing()

    print("\n" + "=" * 80)
    print(" ALL CITATION & SOURCE HANDLING TESTS PASSED 🟢 (100% SUCCESS)")
    print("=" * 80)

if __name__ == "__main__":
    run_all_tests()
