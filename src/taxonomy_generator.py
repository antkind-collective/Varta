import os
import json
import logging
import sqlite3
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

from src.llm_adapter import BaseLLMAdapter, get_llm_adapter

logger = logging.getLogger("VARTA.TaxonomyGenerator")

@dataclass
class CategoryDefinition:
    code: str
    name: str
    definition: str
    inclusion_rules: List[str]
    exclusion_rules: List[str]
    example_indicators: List[str] = field(default_factory=list)

@dataclass
class TaxonomyDimension:
    dimension_id: str
    name: str
    description: str
    is_multi_label: bool
    categories: List[CategoryDefinition]

@dataclass
class GeneratedTaxonomy:
    project_title: str
    research_objectives_summary: str
    dimensions: List[TaxonomyDimension]
    dataset_sample_size: int
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        md = []
        md.append(f"# Dynamic Coding Taxonomy: {self.project_title}\n")
        md.append(f"**Dataset Sample Grounding:** {self.dataset_sample_size} records analyzed  ")
        md.append(f"**Generated:** {self.created_at}  \n")
        md.append(f"### Research Context Alignment\n{self.research_objectives_summary}\n")
        md.append("---\n")

        for dim in self.dimensions:
            md.append(f"## Dimension: {dim.name} (`{dim.dimension_id}`)")
            md.append(f"*{dim.description}*  ")
            md.append(f"**Multi-label:** {'Yes' if dim.is_multi_label else 'No (Mutually Exclusive)'}\n")
            
            md.append("| Code | Category Name | Operational Definition | Inclusion Rules / Key Indicators | Exclusion / Disambiguation |")
            md.append("| :--- | :--- | :--- | :--- | :--- |")
            for cat in dim.categories:
                inc = "<br>• ".join(cat.inclusion_rules) if cat.inclusion_rules else "N/A"
                if cat.inclusion_rules:
                    inc = "• " + inc
                exc = "<br>• ".join(cat.exclusion_rules) if cat.exclusion_rules else "N/A"
                if cat.exclusion_rules:
                    exc = "• " + exc
                md.append(f"| `{cat.code}` | **{cat.name}** | {cat.definition} | {inc} | {exc} |")
            md.append("\n---\n")

        return "\n".join(md)


class TaxonomyGenerator:
    """
    Inducto-Deductive Coding Taxonomy Generator for VARTA:
    Synthesizes top-down research objectives (Research Brief) with bottom-up empirical patterns 
    (Dataset Sample) to produce rigorous, auditable categorical coding schemas.
    """

    def __init__(self, llm_adapter: Optional[BaseLLMAdapter] = None):
        self.llm_adapter = llm_adapter or get_llm_adapter()

    def sample_from_sqlite(
        self,
        sqlite_path: str,
        sample_size: int = 500,
        table_name: str = "chunk_metadata"
    ) -> List[Dict[str, Any]]:
        """Extracts a stratified sample of content and metadata from the SQLite store."""
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        
        # Stratified sampling across source types or parent docs
        query = f"""
            SELECT vector_id, title, content, source_type, source_url, parent_doc_id
            FROM {table_name}
            WHERE content IS NOT NULL AND length(content) > 60
            ORDER BY RANDOM()
            LIMIT {sample_size}
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        sample = []
        for r in rows:
            sample.append({
                "id": r[0],
                "title": r[1] or "Untitled",
                "text_snippet": (r[2][:350] + "...") if len(r[2]) > 350 else r[2],
                "source_type": r[3],
                "source_url": r[4]
            })
        return sample

    def generate_taxonomy(
        self,
        research_brief: str,
        dataset_sample: List[Dict[str, Any]],
        project_title: str = "Disaster & Environmental Analysis",
        target_dimensions_count: int = 4
    ) -> GeneratedTaxonomy:
        """
        Executes LLM inducto-deductive taxonomy generation.
        """
        import datetime
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Compact sample serialization for prompt efficiency
        compact_samples = []
        for idx, item in enumerate(dataset_sample[:100], 1):  # representative slice for LLM context
            title = item.get('title', 'Untitled')
            snippet = item.get('text_snippet', '').replace('\n', ' ').strip()
            src = item.get('source_type', 'Unknown')
            compact_samples.append(f"[{idx}] (Source: {src}) Title: {title} | Excerpt: {snippet}")

        sample_block = "\n".join(compact_samples)

        prompt = f"""You are a Principal Computational Social Scientist and Qualitative Methodology Expert.

You are designing an operational CODING TAXONOMY for a quantitative text analysis project.
The taxonomy must allow an automated classification pipeline to code every document in the corpus into discrete categorical variables for statistical computation (percentages, cross-tabulations, margins of error).

=========================================
1. RESEARCH BRIEF (THEORETICAL INTENT)
=========================================
{research_brief}

=========================================
2. EMPIRICAL DATASET SAMPLE (OBSERVED REALITY)
=========================================
Here is a representative sample of documents from the actual corpus:
{sample_block}

=========================================
DESIGN INSTRUCTIONS & METHODOLOGY:
=========================================
1. Combine top-down research questions (from the brief) with bottom-up patterns (observed in the data).
2. Generate exactly {target_dimensions_count} core analytical dimensions.
3. For each dimension:
   - Provide a clear dimension ID (e.g. `dim_temporal_phase`, `dim_causal_attribution`, `dim_primary_frame`, `dim_action_stance`).
   - Define whether it is single-choice (mutually exclusive) or multi-label.
   - Define 4 to 6 exhaustive and mutually distinct categories.
   - For every category, provide:
     * Code (e.g., C1, C2, F1, F2...)
     * Name
     * Operational Definition (precise academic boundary)
     * Positive Inclusion Rules (linguistic markers, keywords, verbs, themes that trigger this code)
     * Negative/Disambiguation Rules (what distinguishes this from adjacent categories)

4. Return your output strictly as a valid JSON object with the following structure:
{{
  "project_title": "{project_title}",
  "research_objectives_summary": "Summary of how this taxonomy serves the research brief...",
  "dimensions": [
    {{
      "dimension_id": "dim_causal_attribution",
      "name": "Causal Attribution & Responsibility",
      "description": "How the cause of the disaster or impact is framed...",
      "is_multi_label": false,
      "categories": [
        {{
          "code": "C1",
          "name": "Natural Meteorological Driver",
          "definition": "...",
          "inclusion_rules": ["Rule 1", "Rule 2"],
          "exclusion_rules": ["Exclusion 1", "Exclusion 2"],
          "example_indicators": ["heavy monsoon", "cloudburst", "flash flood"]
        }}
      ]
    }}
  ]
}}

Output ONLY the raw JSON block without markdown formatting or conversational filler.
"""

        raw_resp = self.llm_adapter.generate(
            prompt=prompt,
            temperature=0.2,
            max_tokens=4000
        )

        response_text = raw_resp.get("text", "") if isinstance(raw_resp, dict) else str(raw_resp)

        # Clean potential markdown wrapping
        clean_json = response_text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()

        data = json.loads(clean_json)

        dimensions = []
        for d in data.get("dimensions", []):
            cats = []
            for c in d.get("categories", []):
                cats.append(CategoryDefinition(
                    code=c.get("code", ""),
                    name=c.get("name", ""),
                    definition=c.get("definition", ""),
                    inclusion_rules=c.get("inclusion_rules", []),
                    exclusion_rules=c.get("exclusion_rules", []),
                    example_indicators=c.get("example_indicators", [])
                ))
            dimensions.append(TaxonomyDimension(
                dimension_id=d.get("dimension_id", ""),
                name=d.get("name", ""),
                description=d.get("description", ""),
                is_multi_label=d.get("is_multi_label", False),
                categories=cats
            ))

        return GeneratedTaxonomy(
            project_title=data.get("project_title", project_title),
            research_objectives_summary=data.get("research_objectives_summary", ""),
            dimensions=dimensions,
            dataset_sample_size=len(dataset_sample),
            created_at=now_str
        )
