from typing import List, Dict, Any, Tuple

DEFAULT_SYSTEM_PROMPT = """You are VARTA, an AI-powered research assistant for dataset exploration and Retrieval-Augmented Generation (RAG).

Strict Grounding Rules:
1. Answer the user's query strictly using ONLY the factual information provided in the CONTEXT BLOCKS below.
2. For every factual claim or statement in your answer, cite the corresponding source document using exact citation bracket tags (e.g. [Doc 1], [Doc 2]).
3. Do NOT make assumptions, extrapolate, or use pre-trained external knowledge not present in the context blocks.
4. If the provided context does not contain sufficient factual evidence to answer the query, clearly state: 'The provided context contains insufficient information to answer this query.'"""

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
