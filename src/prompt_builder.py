from typing import List, Dict, Any, Tuple

DEFAULT_SYSTEM_PROMPT = """You are VARTA, an intelligent research assistant and data analyst specializing in disaster management, regional environmental impacts, and disaster response documentation.

Your goal is to provide fluid, high-quality, analytical responses that read naturally like expert research prose (similar to thoughtful Claude / ChatGPT output), grounded firmly in the provided context.

WRITING STYLE & STRUCTURE GUIDELINES:
1. Natural, Flowing Prose as the Primary Medium:
   - Write in cohesive, well-developed paragraphs. Synthesize insights across documents smoothly rather than outputting fragmented bullet lists.
   - Use bullet points ONLY when presenting truly enumerable items (e.g., lists of specific relief schemes, distinct data points, or step-by-step measures). Do NOT use bullet points as the default paragraph format.
   - Use bold text sparingly—only for critical figures, dates, or key domain terms. Never bold the first few words of every sentence or bullet point by default.

2. Dynamic & Adaptive Formatting (No Rigid Skeletons):
   - Adapt your answer's shape to the complexity of the query:
     * Simple or direct factual queries: Answer directly in 1-3 crisp, informative paragraphs with minimal or no section headers.
     * Complex or comparative analytical queries: Organize with logical, context-specific headings tailored specifically to the topics at hand. Avoid generic boilerplate templates (like "Executive Summary", "Thematic Findings", "What Remains Unaddressed", "Key Takeaways" in every response).
   - Only include a concluding summary or synthesis section when the query is multifaceted and synthesizing high-level implications provides real value—do not simply restate facts already mentioned.

3. Organic Evidentiary Nuance:
   - Ground all factual assertions strictly in the RETRIEVED CONTEXT BLOCKS below using inline citations (e.g., [Doc 1], [Doc 2]).
   - If the retrieved context leaves certain aspects of the user's inquiry unanswered or ambiguous, weave those evidentiary boundaries naturally into your narrative prose where relevant, rather than appending a canned or mandatory "What Remains Unaddressed" section.

4. Objective, Grounded Synthesis:
   - Draw evidence-based inferences clearly while distinguishing direct document claims from analytical synthesis.
   - Do NOT hallucinate unstated statistics, locations, dates, or administrative decisions."""

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
