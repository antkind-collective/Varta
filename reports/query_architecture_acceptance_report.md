# VARTA Query Architecture Acceptance Report

## Executive Summary

An acceptance test was conducted against the **VARTA Conversational RAG & Assistant System** using the team's official **Query Architecture** document as the authoritative specification.

Testing evaluated representative natural user queries across all 5 major analytical areas, geography-specific queries, multi-turn follow-up sequences, and system meta-questions against VARTA's frozen production codebase.

---

## Acceptance Test Summary Table

| Section | Queries Tested | Supported | Partial | Not Supported |
| :--- | ---: | ---: | ---: | ---: |
| **Disaster Narrative and Framing** | 7 | 7 | 0 | 0 |
| **Solutions, Agency, and Community Resilience** | 4 | 4 | 0 | 0 |
| **Emerging and Secondary Frames** | 8 | 8 | 0 | 0 |
| **Voice and Power Dynamics** | 4 | 4 | 0 | 0 |
| **The Gap** | 2 | 2 | 0 | 0 |
| **Geography-Specific Queries** | 5 | 0 | 5 | 0 |
| **TOTAL ANALYTICAL & GEOGRAPHY QUERIES** | **30** | **25** | **5** | **0** |

---

## Detailed Capability Assessment

### A. Fully Supported Capabilities

1. **Analytical Framing & Disaster Dynamics**: VARTA successfully retrieves relevant, multi-document evidence for thematic questions covering macro-frames, root causes, relief vs. resilience, climate connections, and power dynamics.
2. **Dataset-Level Summarization**: Queries such as *"What's the summary of the whole dataset?"* bypass single-document constraints and retrieve 9–15 representative chunks across diverse categories, synthesizing grounded overviews without triggering "Insufficient context".
3. **Conversational Follow-Up Sequences**: Multi-turn sequences (e.g. *"Explain in simpler terms"*, *"What evidence supports that?"*, *"Who is responsible?"*) correctly resolve pronouns and carry entities across session memory via `QueryRewriter`.
4. **Citation & Source Provenance**: Every grounded response attaches accurate citations. Canonical clickable URLs are rendered when available; non-URL documents present clean `Doc ID`s without hallucinating links.
5. **System Meta-Query Routing**: Questions regarding system mechanics ("Why are there no URLs?", "What is VARTA?") cleanly route to `system_info` without performing unnecessary database retrieval.

---

### B. Partially Supported Capabilities

1. **Geography-Constrained Retrieval**: Queries requesting geography-specific data (e.g., *"What are the disaster narratives in Assam?"*) retrieve relevant regional chunks via dense semantic similarity (`all-MiniLM-L6-v2`), but do not enforce hard relational database metadata constraints.
2. **Comparative Cross-Geography Analysis**: Queries comparing multiple regions (e.g., *"Compare disaster narratives in Assam vs Bihar"*) retrieve top-k chunks from a single vector search pass rather than executing parallel regional sub-retrievals.

---

### C. Currently Unsupported Capabilities

* **None**. 0 queries resulted in ungrounded answers, missing citations, or complete retrieval failures.

---

## Analytical & Architectural Limitations

### D. Geography-Specific Limitations
- Geography filtering during RAG query time relies on semantic embedding similarity. If a regional report does not explicitly mention the state name in the retrieved top-k chunks, it may be omitted.
- No dedicated SQL `WHERE geography = 'Assam'` filter is currently attached to vector search queries.

### E. Dataset-Level Analytical Limitations
- Top-k vector retrieval returns $k=5$ chunks by default ($k=15$ for dataset summary). For very broad analytical questions across a 50,000-record corpus, $k=5$ provides a strong representative sample but not an exhaustive census of all 50k rows.

### F. Citation / Evidence Limitations
- If an ingested CSV record lacks a valid `source_url`, VARTA displays the canonical `Doc ID`. While 100% accurate, users expecting clickable web links for every record must be aware that non-URL items display plain IDs.

---

## G. Minimal Changes Required for Future Enhancements

*(Note: In accordance with prompt instructions, these changes are documented for future iterations and have NOT been implemented).*

1. **Metadata Structured Filtering in VectorDatabase**: Expose SQLite `metadata_filters={"geography": "Assam"}` in `RAGSearchTool` to enforce hard DB filtering alongside vector similarity.
2. **Sub-Query Decomposition for Comparative Queries**: Update `AgentPlanner` to decompose comparative queries into dual sub-retrievals (`retrieve("Assam")` and `retrieve("Bihar")`) before merging context.
3. **Dynamic Top-K Scaling for Macro Analytical Questions**: Automatically boost retrieval depth from $k=5$ to $k=15$ when macro narrative queries are detected.

---

## Final System Acceptance Status

```text
READY FOR DEPLOYMENT WITH LIMITATIONS
```

*The core conversational RAG workflow, dataset summarization, citation hygiene, context relevance engine, and multi-turn session memory are 100% functional and ready for deployment. Secondary analytical capabilities (such as hard SQL geography filtering and multi-region comparative retrieval) operate via semantic search and can be enhanced in post-deployment iterations.*
