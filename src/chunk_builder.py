import re
from typing import List, Dict, Any, Optional

class ChunkBuilder:
    """
    Recursive Character Chunking Module for VARTA Phase 2:
    - Recursively splits document text using natural separators (paragraphs, lines, sentences).
    - Preserves title as a distinct standalone metadata field.
    - Computes embedding_text with optional title header injection.
    - Inherits parent metadata and maintains parent-child referential linkage.
    """

    def __init__(
        self,
        target_chunk_size: int = 1200,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
        inject_title_header: bool = True
    ):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", "। ", ". ", " ", ""]
        self.inject_title_header = inject_title_header

    def _split_text_recursively(self, text: str, separators: List[str]) -> List[str]:
        """Hierarchical recursive text splitting algorithm."""
        final_chunks = []
        if not text or len(text) <= self.target_chunk_size:
            return [text] if text else []

        # Find the highest priority separator present in the text
        sep = separators[-1]
        for s in separators:
            if s in text:
                sep = s
                break

        splits = text.split(sep) if sep != "" else list(text)

        current_chunk = ""
        for part in splits:
            part_str = part + sep if sep != "" else part
            if len(current_chunk) + len(part_str) <= self.target_chunk_size:
                current_chunk += part_str
            else:
                if current_chunk.strip():
                    final_chunks.append(current_chunk.strip())
                # If a single split part exceeds chunk size, recurse on remaining separators
                if len(part_str) > self.target_chunk_size and len(separators) > 1:
                    sub_chunks = self._split_text_recursively(part_str, separators[separators.index(sep) + 1:])
                    final_chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = part_str

        if current_chunk.strip():
            final_chunks.append(current_chunk.strip())

        # Apply overlap processing between adjacent chunks if requested
        if self.chunk_overlap > 0 and len(final_chunks) > 1:
            overlapped_chunks = []
            for idx, chk in enumerate(final_chunks):
                if idx == 0:
                    overlapped_chunks.append(chk)
                else:
                    prev_tail = final_chunks[idx - 1][-self.chunk_overlap:]
                    overlapped_chunks.append(prev_tail + " " + chk)
            return overlapped_chunks

        return final_chunks

    def build_chunks_from_document(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        parent_doc_id = doc.get("doc_id", "")
        title = doc.get("title")
        content = doc.get("content", "")
        metadata = doc.get("metadata", {})

        # If content is short enough, create 1 single chunk without splitting overhead
        if len(content) <= self.target_chunk_size:
            raw_chunks = [content]
        else:
            raw_chunks = self._split_text_recursively(content, self.separators)

        total_chunks = len(raw_chunks)
        chunk_objects = []

        for idx, chunk_text in enumerate(raw_chunks):
            chunk_id = f"{parent_doc_id}#chunk_{idx:03d}"
            
            # Format embedding_text (title injection for embedding model)
            if self.inject_title_header and title:
                embedding_text = f"Title: {title}\nContent: {chunk_text}"
            else:
                embedding_text = chunk_text

            chunk_obj = {
                "chunk_id": chunk_id,
                "parent_doc_id": parent_doc_id,
                "chunk_index": idx,
                "total_chunks": total_chunks,
                "title": title,
                "content": chunk_text,
                "embedding_text": embedding_text,
                "char_count": len(chunk_text),
                "word_count": len(chunk_text.split()),
                "metadata": metadata
            }
            chunk_objects.append(chunk_obj)

        return chunk_objects
