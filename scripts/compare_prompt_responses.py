import os
import sys
import json
import time
from pathlib import Path

# Ensure project root is in sys.path
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from dotenv import load_dotenv
load_dotenv()

from src.prompt_builder import PromptBuilder, DEFAULT_SYSTEM_PROMPT
from src.vector_database import VectorDatabase
from src.semantic_retriever import SemanticRetriever
from src.embedding_providers import get_embedding_provider
from src.llm_adapter import get_llm_adapter
from src.rag_orchestrator import RAGOrchestrator

OLD_SYSTEM_PROMPT = """You are VARTA, an expert AI research analyst and intelligent retrieval assistant specializing in disaster management, regional environmental impacts, and data analysis.

CORE REASONING & SYNTHESIS GUIDELINES:
1. Natural AI Reasoning & Constructive Synthesis:
   - Reason thoughtfully over all relevant context provided. Synthesize insights, identify themes, and draw logical connections across documents.
   - NEVER flatly refuse an answer or output canned "insufficient information" disclaimers if partial or related relevant context exists.
   - If the retrieved context answers part of the user's question, provide a detailed, well-reasoned answer for that part, and specifically note what remains unaddressed or absent in the documents.

2. Strict Grounding & Inline Citations:
   - Base all factual claims, data points, quotes, and specific findings strictly on the RETRIEVED CONTEXT BLOCKS below.
   - Cite source documents inline using exact bracket tags (e.g. [Doc 1], [Doc 2]).
   - Do NOT fabricate facts, dates, numbers, or events not supported by the context. When interpreting or drawing inferences, make it clear that it is an evidence-based inference.

3. Meta & Dataset Inquiries:
   - When asked about dataset coverage, source platforms (e.g., Reddit, news dispatches, government bulletins), or specific topics, summarize what the corpus contains and describe the scope of available records.

4. Formatting & Structure:
   - Use clear markdown structure: executive summaries, thematic sections, bullet points, and highlighted key takeaways."""

TEST_QUERIES = [
    {
        "type": "Simple Factual",
        "query": "Which NDRF teams or defense personnel were deployed for rescue operations during the Assam floods?"
    },
    {
        "type": "Specific Operational Status",
        "query": "What was the disruption to railway services in the Lumding-Badarpur hill section?"
    },
    {
        "type": "Complex Policy Synthesis",
        "query": "What specific government relief packages or compensation were announced for flood-affected families and farmers?"
    },
    {
        "type": "Comparative Analytical Evaluation",
        "query": "Is there a difference between how official authorities describe flood mitigation progress versus community concerns over recurrent embankment breaches?"
    }
]

def run_comparison():
    print("=" * 80)
    print("RUNNING BEFORE / AFTER PROMPT COMPARISON SUITE")
    print("=" * 80)
    
    vdb_dir = root / "data" / "vector_db"
    vdb = VectorDatabase.load(str(vdb_dir))
    provider = get_embedding_provider()
    llm = get_llm_adapter()
    retriever = SemanticRetriever(vector_db=vdb, embedding_provider=provider)
    
    results = []
    
    for item in TEST_QUERIES:
        q_type = item["type"]
        q_text = item["query"]
        print(f"\nEvaluating Query Type [{q_type}]: '{q_text}'")
        
        # 1. Run with OLD Prompt
        orch_old = RAGOrchestrator(
            retriever=retriever,
            llm_adapter=llm,
            prompt_builder=PromptBuilder(system_prompt=OLD_SYSTEM_PROMPT),
            max_context_tokens=3500
        )
        res_old = orch_old.run_pipeline(q_text, top_k=5)
        ans_old = res_old.get("answer", "")
        
        # 2. Run with NEW Adaptive Prompt
        orch_new = RAGOrchestrator(
            retriever=retriever,
            llm_adapter=llm,
            prompt_builder=PromptBuilder(system_prompt=DEFAULT_SYSTEM_PROMPT),
            max_context_tokens=3500
        )
        res_new = orch_new.run_pipeline(q_text, top_k=5)
        ans_new = res_new.get("answer", "")
        
        results.append({
            "query_type": q_type,
            "query": q_text,
            "before_old_prompt": ans_old,
            "after_new_prompt": ans_new
        })
        
    out_file = root / "reports" / "prompt_rewrite_comparison.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"\nSaved detailed comparison JSON to {out_file}")

if __name__ == "__main__":
    run_comparison()
