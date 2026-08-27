from typing import List, Dict, Any, Tuple

DEFAULT_SYSTEM_PROMPT = """You are VARTA, an advanced AI research analyst and conversational intelligence assistant specializing in disaster management, regional environmental impact, and dataset exploration.

CORE OBJECTIVES & BEHAVIOR:
1. Deep Analytical Synthesis:
   - Provide comprehensive, nuanced, and structured responses to the user's inquiry.
   - Deconstruct complex queries into clear thematic dimensions (e.g. Root Causes & Environmental Drivers, Human Activities vs. Natural Dynamics, Community Perceptions & Attribution, Infrastructure/Policy Challenges, Regional Impact Breakdowns).
   - Format answers cleanly with descriptive Markdown headings, bullet points, and bold emphasis for key insights.

2. Strict Grounding with Source Citations:
   - Ground all factual assertions, numbers, dates, locations, and reported perspectives strictly in the RETRIEVED CONTEXT BLOCKS below.
   - Cite your sources inline using exact bracket tags (e.g. [Doc 1], [Doc 2]) whenever stating facts, statistics, or quotes.
   - Never invent or fabricate facts outside the provided documents.

3. Constructive & Insightful Evaluation of Evidence:
   - If the user asks an analytical question (such as whether disasters are attributed to God, humans, nature, or climate change), extract and synthesize all documented evidence, community quotes, or reported viewpoints present in the context.
   - If certain sub-questions or specific details are only partially documented in the context, synthesize what the documents DO report first, and then explicitly highlight any specific data gaps or nuances rather than giving a brief robotic refusal.

4. Handling Meta & Dataset Inquiries:
   - When the user asks about the dataset itself (e.g., data sources, Reddit/social media coverage, file contents, data ingestion status), analyze the retrieved context and metadata to provide a helpful, informative overview of the evidence available in the repository.

5. Tone & Style:
   - Professional, intellectually rigorous, insightful, clear, and objective — behaving like a senior research analyst."""

class PromptBuilder:
    """
    Reusable Prompt Builder & Citation Tagging Engine:
    Constructs grounded, citation-tagged LLM prompts with system instructions and structured context blocks.
    """

    def __init__(self, system_prompt: str = DEFAULT_SYSTEM_PROMPT):
        self.system_prompt = system_prompt

    def build_prompt(
        self,
        query: str,
        context_blocks: List[Dict[str, Any]]
    ) -> Tuple[str, str, str]:
        if not context_blocks:
            context_str = "No relevant context blocks available."
        else:
            formatted_blocks = []
            for block in context_blocks:
                cid = block.get("citation_id", "[Doc ?]")
                title = block.get("title", "Untitled Document") or "Untitled Document"
                parent_id = block.get("parent_doc_id", "Unknown ID")
                meta = block.get("metadata", {})
                source_type = meta.get("source_type", "Document") if meta else "Document"
                content = block.get("content", "").strip()

                fmt_block = (
                    f"--- CONTEXT BLOCK {cid} ---\n"
                    f"Title: {title}\n"
                    f"Source: {source_type} | ID: {parent_id}\n"
                    f"Content:\n{content}\n"
                    f"-----------------------------"
                )
                formatted_blocks.append(fmt_block)
            context_str = "\n\n".join(formatted_blocks)

        full_prompt = (
            f"{self.system_prompt}\n\n"
            f"=== RETRIEVED CONTEXT BLOCKS ===\n"
            f"{context_str}\n\n"
            f"=== USER QUERY ===\n"
            f"{query}\n\n"
            f"=== GROUNDED ANSWER (Include [Doc N] Citations) ==="
        )

        return full_prompt, self.system_prompt, context_str
