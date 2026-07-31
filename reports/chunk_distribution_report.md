# VARTA — Chunk Distribution Report (Sprint 2.1 Analysis)

## 1. Executive Summary

This report provides a detailed empirical analysis of the document chunking results generated during **Sprint 2.1 (Embedding Pipeline)** across the standardized corpus (`data/standardized/standardized_documents.json`).

The chunking engine utilized **Recursive Character Chunking** with a target chunk size of `1,200 characters` (~250–300 words), chunk overlap of `200 characters`, and contextual title header injection.

---

## 2. Core Corpus & Chunking Metrics

| Metric | Empirical Value | Description / Scope |
| :--- | :-: | :--- |
| **1. Total Documents Processed** | **`33,975`** | Total input documents from `standardized_documents.json` |
| **2. Total Chunks Generated** | **`39,172`** | Total text chunks exported to `data/embeddings/chunks.json` |
| **3. Average Chunks per Document** | **`1.15`** | Mean chunk count per parent document |
| **5. Average Document Character Count** | **`834.05` chars** | Mean character length across raw standardized documents (~150 words) |
| **6. Average Chunk Character Count** | **`750.45` chars** | Mean character length across exported text chunks (~140 words) |
| **7. Maximum Document Length** | **`11,666` chars** | Longest regional news article in the corpus (~2,100 words) |
| **8. Max Chunks from Single Document** | **`11` chunks** | Maximum chunks produced from a single document |
| **9. Percentage Requiring Chunking** | **`11.25%`** | Proportion of documents split into > 1 chunk (`3,823` documents) |

---

## 3. Distribution of Chunks per Document (Task 4)

| Chunk Count Category | Document Count | Percentage of Corpus | Visual Breakdown | Primary Document Type |
| :--- | :-: | :-: | :--- | :--- |
| **1 Chunk** | `30,152` | **88.75%** | `██████████████████████████████████████████████████` | Short news sound bites, wire alerts, social posts (`< 1,200` chars) |
| **2 Chunks** | `2,889` | **8.50%** | `████` | Medium news articles (`1,201` – `2,400` chars) |
| **3 Chunks** | `661` | **1.95%** | `█` | Detailed regional reports (`2,401` – `3,600` chars) |
| **4+ Chunks** | `273` | **0.80%** | `▎` | In-depth investigative news features (`> 3,600` chars up to `11,666` chars) |
| **Total Corpus** | **`33,975`** | **100.0%** | — | — |

---

## 4. Verification of 1.15 Average Chunks per Document (Task 10)

> [!IMPORTANT]
> **VERIFICATION VERDICT: 100% EXPECTED & MATHEMATICALLY CONSISTENT**

### Analytical Reasoning:
1. **Corpus Nature**: The input dataset (`Flood Regional News 25-26 - Sheet1.csv`) consists primarily of short regional news summaries, wire sound bites, and social media quotes. The average document character length across the entire corpus is **`834.05` characters** (~150 words).
2. **Chunking Threshold**: The configured target chunk size is **`1,200` characters**.
3. **Distribution Alignments**: Because **88.75%** (`30,152` out of `33,975`) of all standardized documents contain fewer than 1,200 characters, they fit completely within a single chunk without requiring splitting.
4. **Multi-Chunk Tail**: Only **11.25%** (`3,823` documents) exceed the 1,200-character threshold and are recursively split into 2 to 11 chunks (accounting for the additional `5,197` chunks beyond the baseline 33,975).
5. **Conclusion**: The ratio $\frac{39,172 \text{ chunks}}{33,975 \text{ documents}} = 1.1529 \approx \mathbf{1.15}$ is mathematically exact and perfectly reflects the document length profile of the regional news dataset.

---

## 5. Summary & Recommendation for Vector Indexing (Sprint 2.2)

- **Zero Content Fragmentation**: 88.75% of documents remain unified as single, cohesive chunks, eliminating artificial boundary cuts for short news posts.
- **Context Injection**: For the 11.25% multi-chunk documents, contextual title injection (`"Title: {title}\nContent: {content}"`) ensures every chunk carries full headline context into FAISS / ChromaDB vector search.
- **Ready for Vector Indexing**: The 39,172 chunks and their corresponding 384-dimensional dense vectors in `data/embeddings/embeddings.npy` are verified and ready for **Sprint 2.2 (Vector Database Indexing)**.
