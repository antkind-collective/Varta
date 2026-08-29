import os
import sys
import json
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.llm_adapter import get_llm_adapter
from src.prompt_builder import PromptBuilder

def run_reasoning_benchmark():
    print("=" * 80)
    print("VARTA MODEL REASONING & ANALYTICAL CAPABILITY BENCHMARK")
    print("=" * 80)

    adapter = get_llm_adapter()
    prompt_builder = PromptBuilder()
    
    print(f"\n[Active Model]: {adapter.get_model_name()} ({adapter.__class__.__name__})")

    # Benchmark Test Suite
    benchmarks = [
        {
            "category": "1. Multi-Step Causal & Environmental Synthesis",
            "query": "What are the primary drivers of severe flooding in Assam, and how do human infrastructure decisions interact with natural river dynamics?",
            "context_blocks": [
                {
                    "citation_id": "[Doc 1]",
                    "title": "Dibrugarh prepares for Brahmaputra floods with early plans",
                    "parent_doc_id": "mo-sn-59312710965",
                    "metadata": {"source_type": "News Article"},
                    "content": "The Brahmaputra river carries massive sediment loads from the eastern Himalayas during the monsoon season. Heavy siltation raises the riverbed, reducing the channel's carrying capacity and causing widespread water spillover across Dibrugarh and adjacent plains. Embankments built along the banks often breach due to hydraulic pressure, trapping floodwaters in human settlements."
                },
                {
                    "citation_id": "[Doc 2]",
                    "title": "Relentless Floods Wreak Havoc In Assam, Over 2.2K Dead In 26 Years",
                    "parent_doc_id": "mo-sn-60051436804",
                    "metadata": {"source_type": "Analytical Report"},
                    "content": "A report reveals that over 2,200 people lost their lives in Assam floods over the past 26 years. Experts point to rapid deforestation in upper catchment areas, unscientific drainage blocking, wetland encroachment in urban hubs like Guwahati, and poorly maintained earthen embankments as key accelerators of catastrophic inundation."
                },
                {
                    "citation_id": "[Doc 3]",
                    "title": "Train services hit in upper Assam after tracks inundated",
                    "parent_doc_id": "mo-sn-60036351281",
                    "metadata": {"source_type": "Field Dispatch"},
                    "content": "Continuous cloudburst-induced downpours in neighboring Arunachal hills caused flash floods in Dhemaji and Lakhimpur. Inundation submerged railway tracks and cut off road networks, forcing NDRF and SDRF teams to evacuate 2,000 passengers."
                }
            ]
        },
        {
            "category": "2. Attribution, Beliefs vs. Empirical Causes (Nuance & Disentanglement)",
            "query": "How do local communities in disaster-prone river basins perceive the causes of recurrent floods? Do records attribute disasters to divine wrath, climate change, or human administrative failure?",
            "context_blocks": [
                {
                    "citation_id": "[Doc 1]",
                    "title": "Community Voices: Living with the Mighty Brahmaputra",
                    "parent_doc_id": "comm-rep-88129",
                    "metadata": {"source_type": "Field Survey"},
                    "content": "Elderly villagers in Majuli and Barpeta historically revered the Brahmaputra river as a living deity ('Burha Luit'), viewing regular annual inundations as natural blessings that rejuvenate agricultural soil. However, younger residents and local activists increasingly blame government corruption in embankment construction and upstream dam releases for turning natural floods into sudden human-made disasters."
                },
                {
                    "citation_id": "[Doc 2]",
                    "title": "Changing Monsoon Patterns and Extreme Weather in Northeast India",
                    "parent_doc_id": "cli-sci-10294",
                    "metadata": {"source_type": "Research Publication"},
                    "content": "Meteorological data indicates a noticeable shift from prolonged moderate rainfall to brief, high-intensity extreme precipitation events. While localized myths sometimes interpret abnormal deluges as divine displeasure, scientific analyses attribute the shifting precipitation intensity directly to regional climate variability and warming Bay of Bengal sea temperatures."
                }
            ]
        },
        {
            "category": "3. Contradiction & Evidence Discrepancy Analysis",
            "query": "Compare the reported casualty figures and causes for the recent bridge collapse and flash flood in the region. Are the figures consistent across sources?",
            "context_blocks": [
                {
                    "citation_id": "[Doc 1]",
                    "title": "Preliminary State Disaster Management Authority Briefing",
                    "parent_doc_id": "sdma-brief-01",
                    "metadata": {"source_type": "Official Report"},
                    "content": "As of 18:00 hrs, the State Disaster Management Authority officially confirmed 12 casualties and 4 missing persons following the sudden breach of the river culvert under intense 150mm rainfall."
                },
                {
                    "citation_id": "[Doc 2]",
                    "title": "Local Eyewitness & Hospital Casualty Log",
                    "parent_doc_id": "hosp-log-902",
                    "metadata": {"source_type": "Medical Dispatch"},
                    "content": "District civil hospital authorities stated that 28 bodies have been received from the collapsed bridge site. Local community leaders allege that overloaded commercial trucks ignoring weight restrictions weakened the structural pillars prior to the water surge."
                }
            ]
        }
    ]

    results = []

    for idx, test in enumerate(benchmarks, 1):
        print("\n" + "=" * 80)
        print(f"BENCHMARK {idx}: {test['category']}")
        print(f"User Query: \"{test['query']}\"")
        print("-" * 80)

        full_prompt, _, _ = prompt_builder.build_prompt(
            query=test["query"],
            context_blocks=test["context_blocks"]
        )

        start_time = time.time()
        try:
            llm_resp = adapter.generate(full_prompt)
            gen_text = llm_resp.get("text", "") if isinstance(llm_resp, dict) else str(llm_resp)
            duration = round(time.time() - start_time, 2)
            
            print(f"\n[Generated Response] ({duration}s):\n")
            print(gen_text)

            # Automated Reasoning Evaluation Criteria
            has_citations = "[Doc 1]" in gen_text or "[Doc 2]" in gen_text
            has_structure = "#" in gen_text or "**" in gen_text
            word_count = len(gen_text.split())
            is_deep = word_count > 100

            print("\n[Evaluation Checks]:")
            print(f"  - Grounded Citations Present: {'YES [PASS]' if has_citations else 'NO [FAIL]'}")
            print(f"  - Structured Formatting (Headings/Bullets): {'YES [PASS]' if has_structure else 'NO [FAIL]'}")
            print(f"  - Analytical Depth & Word Count: {word_count} words ({'DEEP [PASS]' if is_deep else 'TOO BRIEF [FAIL]'})")

            results.append({
                "test": test["category"],
                "success": has_citations and has_structure and is_deep,
                "duration": duration,
                "word_count": word_count
            })

        except Exception as e:
            print(f"[ERROR]: {e}")
            results.append({
                "test": test["category"],
                "success": False,
                "error": str(e)
            })

    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)
    for r in results:
        status = "PASSED" if r.get("success") else "FAILED"
        print(f"- {r['test']}: {status} ({r.get('word_count', 0)} words, {r.get('duration', 0)}s)")

if __name__ == "__main__":
    run_reasoning_benchmark()
