import re
from typing import List, Dict, Any

class ContextAssembler:
    """
    Context Assembler & Overlapping Chunk Merger:
    - Deduplicates redundant chunks
    - Merges adjacent chunks from the same parent document to preserve context continuity
    - Formats clean citation tags ([Doc 1], [Doc 2])
    - Preserves metadata provenance
    """

    def __init__(self, merge_overlapping_chunks: bool = True):
        self.merge_overlapping_chunks = merge_overlapping_chunks

    def assemble_context(self, retrieved_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not retrieved_chunks:
            return []

        # 1. Deduplicate by chunk_id
        unique_chunks = []
        seen_ids = set()
        for chunk in retrieved_chunks:
            cid = chunk.get("chunk_id")
            if cid and cid in seen_ids:
                continue
            if cid:
                seen_ids.add(cid)
            unique_chunks.append(chunk)

        if not self.merge_overlapping_chunks:
            # Assign citation IDs directly
            assembled = []
            for idx, c in enumerate(unique_chunks):
                doc_item = dict(c)
                doc_item["citation_id"] = f"[Doc {idx + 1}]"
                assembled.append(doc_item)
            return assembled

        # 2. Group adjacent chunks by parent_doc_id for overlapping merging
        grouped_by_parent: Dict[str, List[Dict[str, Any]]] = {}
        for c in unique_chunks:
            pid = c.get("parent_doc_id", "unknown_parent")
            if pid not in grouped_by_parent:
                grouped_by_parent[pid] = []
            grouped_by_parent[pid].append(c)

        merged_blocks = []
        for pid, group in grouped_by_parent.items():
            # Sort chunks by chunk_index
            sorted_group = sorted(group, key=lambda x: x.get("chunk_index", 0))

            merged_content = ""
            best_chunk = sorted_group[0]
            max_score = max(c.get("similarity_score", 0.0) for c in sorted_group)

            for c in sorted_group:
                content = c.get("content", "").strip()
                if not merged_content:
                    merged_content = content
                else:
                    # Simple overlap trim: check matching suffix/prefix
                    overlap_len = min(200, len(merged_content), len(content))
                    trimmed_content = content
                    for o_size in range(overlap_len, 20, -1):
                        if merged_content.endswith(content[:o_size]):
                            trimmed_content = content[o_size:].strip()
                            break
                    if trimmed_content:
                        merged_content += "\n\n" + trimmed_content

            block = {
                "parent_doc_id": pid,
                "title": best_chunk.get("title"),
                "content": merged_content,
                "similarity_score": max_score,
                "source_chunks_count": len(sorted_group),
                "original_chunk_ids": [c.get("chunk_id") for c in sorted_group],
                "metadata": best_chunk.get("metadata", {})
            }
            merged_blocks.append(block)

        # Re-sort merged blocks by top similarity_score
        merged_blocks.sort(key=lambda x: x.get("similarity_score", -1.0), reverse=True)

        # Assign citation IDs [Doc 1], [Doc 2], ...
        for idx, block in enumerate(merged_blocks):
            block["citation_id"] = f"[Doc {idx + 1}]"

        return merged_blocks
