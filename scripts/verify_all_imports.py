import importlib
import pkgutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def verify_modules():
    print("=" * 80)
    print("VERIFYING ALL MODULE IMPORTS IN SRC AND API")
    print("=" * 80)
    
    modules_to_test = [
        "api.app",
        "api.routes",
        "api.schemas",
        "api.dependencies",
        "src.agent_planner",
        "src.assistant_controller",
        "src.context_relevance_engine",
        "src.context_resolver",
        "src.conversation_manager",
        "src.conversation_memory",
        "src.conversation_validator",
        "src.dataset_ingestor",
        "src.dataset_loader",
        "src.document_builder",
        "src.document_serializer",
        "src.document_validator",
        "src.embedding_providers",
        "src.execution_plan",
        "src.index_builder",
        "src.index_loader",
        "src.llm_adapter",
        "src.metadata_formatter",
        "src.metadata_store",
        "src.planner_validator",
        "src.preprocessing_pipeline",
        "src.query_decomposer",
        "src.query_rewriter",
        "src.rag_orchestrator",
        "src.report_generator",
        "src.retrieval_engine",
        "src.retrieval_executor",
        "src.semantic_retriever",
        "src.session",
        "src.taxonomy_generator",
        "src.tool_registry",
        "src.tool_router",
        "src.tool_validator",
        "src.vector_database",
    ]
    
    failed = []
    for mod_name in modules_to_test:
        try:
            mod = importlib.import_module(mod_name)
            print(f"  [OK] {mod_name}")
        except Exception as e:
            print(f"  [FAILED] {mod_name}: {e}")
            failed.append((mod_name, str(e)))
            
    print("\n" + "=" * 80)
    if failed:
        print(f"FAILED MODULES ({len(failed)}):")
        for m, err in failed:
            print(f"  - {m}: {err}")
        sys.exit(1)
    else:
        print("ALL 38 MODULES IMPORTED CLEANLY WITH ZERO ERRORS!")
        print("=" * 80)

if __name__ == "__main__":
    verify_modules()
