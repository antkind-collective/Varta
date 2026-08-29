import sys
import os
import json
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.taxonomy_generator import TaxonomyGenerator

RESEARCH_BRIEF = """PROJECT BRIEF: Regional Flood & Disaster Dynamics in Assam and North-Eastern River Basins

CORE RESEARCH QUESTIONS:
1. Frame Identification: What are the dominant communicative frames through which media, civic groups, and citizens discuss disaster events (e.g. risk/vulnerability assessments of specific localities, disruptions to transport/livelihoods, institutional critiques, humanitarian aid)?
2. Causal Attribution & Blame: How is causation attributed in public and journalistic accounts? Specifically, how do accounts disentangle:
   - Natural/meteorological extremes (cloudbursts, torrential monsoons, upstream river surges)
   - Infrastructure & engineering failures (embankment/dyke breaches, uncoordinated dam releases, blocked drainage channels)
   - Socio-spatial encroachment & urban planning (settlements in flood-prone riverbeds, destruction of natural wetlands)
   - Fatalistic or divine attributions (acts of God, inevitable fate)
   - Descriptive event logging without explicit causal attribution
3. Temporal & Situational Phase: How does discourse shift across the disaster lifecycle:
   - Acute crisis / active hazard (real-time rescue, submergence, flash flood alerts)
   - Post-event recovery & aftermath (damage assessments, compensation, disease management)
   - Non-event & dry-season discourse (retrospective evaluations, seasonal preparedness, policy debates)
4. Public Stance & Action Demands: What emotional and action-oriented stances characterize the text (civic outrage & demand for political accountability vs. resignation & enduring vulnerability vs. community solidarity & mutual aid)?
"""

def main():
    print("=" * 90)
    print("VARTA DYNAMIC TAXONOMY GENERATION PIPELINE")
    print("Testing Inducto-Deductive Synthesis (Research Brief + 500-Row Corpus Sample)")
    print("=" * 90)

    sqlite_path = str(PROJECT_ROOT / "data" / "vector_db" / "metadata.sqlite")
    gen = TaxonomyGenerator()

    print(f"\n[Step 1] Sampling empirical dataset from: {sqlite_path}...")
    sample = gen.sample_from_sqlite(sqlite_path, sample_size=500)
    print(f"  Sampled {len(sample)} unique records across indexed news, blogs, and dispatches.")

    print(f"\n[Step 2] Executing LLM-driven Inducto-Deductive Taxonomy Generation...")
    start_t = time.time()
    taxonomy = gen.generate_taxonomy(
        research_brief=RESEARCH_BRIEF,
        dataset_sample=sample,
        project_title="Assam & Regional Disaster Discourse Study",
        target_dimensions_count=4
    )
    duration = round(time.time() - start_t, 2)
    print(f"  Taxonomy generated successfully in {duration}s!")

    # Save to JSON
    out_dir = PROJECT_ROOT / "data" / "taxonomies"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "generated_disaster_taxonomy.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(taxonomy.to_dict(), f, indent=2, ensure_ascii=False)
    print(f"\n[Step 3] Saved machine-readable taxonomy schema to: {json_path}")

    # Display generated Markdown
    md_output = taxonomy.to_markdown()
    print("\n" + "=" * 90)
    print("GENERATED TAXONOMY REPORT:")
    print("=" * 90)
    print(md_output)

    # Save markdown version as well
    md_path = out_dir / "generated_disaster_taxonomy.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_output)
    print(f"\nSaved human-readable taxonomy report to: {md_path}")

if __name__ == "__main__":
    main()
