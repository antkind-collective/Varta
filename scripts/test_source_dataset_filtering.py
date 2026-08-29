import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.metadata_store import MetadataStore
from src.context_relevance_engine import ResearchContext
from src.rag_orchestrator import RAGOrchestrator
from src.semantic_retriever import SemanticRetriever
from src.vector_database import VectorDatabase

def test_source_dataset_functionality():
    print("==================================================")
    print("TESTING SOURCE_DATASET MIGRATION & SCOPING")
    print("==================================================")

    store = MetadataStore("data/vector_db/metadata.sqlite")

    # 1. Test dataset breakdown
    counts = store.get_total_records_count()
    print(f"\n[Check 1] Total indexed records in SQLite: {counts}")
    assert counts > 0, "Metadata store should contain indexed records"

    # 2. Test scoped retrieval with source_dataset='master_news_corpus'
    vids_master = store.get_scoped_vector_ids(geography=["Assam"], source_dataset="master_news_corpus", limit=50)
    print(f"[Check 2] Scoped vector IDs for Assam in 'master_news_corpus': {len(vids_master)} found")
    assert len(vids_master) > 0, "Should find Assam records in master_news_corpus"

    # 3. Test scoped retrieval with non-existent dataset
    vids_empty = store.get_scoped_vector_ids(geography=["Assam"], source_dataset="non_existent_dataset", limit=50)
    print(f"[Check 3] Scoped vector IDs for Assam in 'non_existent_dataset': {len(vids_empty)} found")
    assert len(vids_empty) == 0, "Non-existent dataset should return 0 scoped vector IDs"

    # 4. Test ResearchContext with source_dataset
    ctx = ResearchContext(
        geography=["Assam"],
        domain="disaster",
        source_dataset="master_news_corpus"
    )
    print(f"[Check 4] ResearchContext initialized with source_dataset: {ctx.source_dataset}")
    assert ctx.source_dataset == "master_news_corpus"

    print("\nALL SOURCE_DATASET PREREQUISITE TESTS PASSED!")

if __name__ == "__main__":
    test_source_dataset_functionality()
