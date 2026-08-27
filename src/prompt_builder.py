from typing import List, Dict, Any, Tuple

DEFAULT_SYSTEM_PROMPT = """You are VARTA, an expert AI research analyst and intelligent retrieval assistant specializing in disaster management, regional environmental impacts, and data analysis.

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
