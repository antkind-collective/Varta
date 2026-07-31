# VARTA — Preprocessing & Vectorization Strategy (Sprint 1.2 Roadmap)

## 1. Executive Summary & Strategy Purpose
This report outlines the recommended preprocessing, metadata preservation, and document standardization strategy for **Sprint 1.2**. **No data modifications have been performed in Sprint 1.1**.

## 2. Text Field Profiling & Noise Summary
| Column | Min / Max Length | Avg / Median Length | Short Records (<20) | Long Records (>1k) | HTML Tags | URLs | Emojis | Linebreaks |
| :--- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| `Sound Bite Text` | 6 / 11,666 | 828.93 / 739.0 | 3 | 7,308 | 0 | 90 | 46 | 4,232 |
| `Title` | 8 / 340 | 76.41 / 71.0 | 143 | 0 | 0 | 0 | 1 | 0 |
| `Unnamed: 4` | 79 / 79 | 79.0 / 79.0 | 0 | 0 | 0 | 4 | 0 | 0 |

## 3. Metadata Evaluation & Column Role Matrix
| Column Name | Category | Strategic Role in RAG Pipeline | Preprocessing Action |
| :--- | :--- | :--- | :--- |
| `Post ID` | **Identifier** | 🔑 Primary Document Reference | Preserve intact as payload metadata `doc_id` / `source_url`. |
| `Sound Bite Text` | **Text** | 🎯 Core Vector Payload | Clean, normalize whitespace, construct document chunk payload. |
| `Title` | **Text** | 🎯 Core Vector Payload | Clean, normalize whitespace, construct document chunk payload. |
| `Source Type` | **Metadata** | 🏷️ Metadata Filter Attribute | Preserve intact as query filtering metadata. |
| `Unnamed: 4` | **Text** | 🎯 Core Vector Payload | Clean, normalize whitespace, construct document chunk payload. |
| `Unnamed: 5` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 6` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 7` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 8` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 9` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 10` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 11` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 12` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 13` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 14` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 15` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 16` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 17` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 18` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 19` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 20` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 21` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 22` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 23` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 24` | **Other** | ❌ Obsolete / Ghost Column | Drop column completely during data ingestion. |
| `Unnamed: 25` | **Categorical** | 🏷️ Metadata Filter Attribute | Preserve intact as query filtering metadata. |
| `Unnamed: 26` | **Categorical** | 🏷️ Metadata Filter Attribute | Preserve intact as query filtering metadata. |

## 4. Preprocessing Recommendations for Sprint 1.2

### A. Missing Value Handling
1. **Text Columns (`Sound Bite Text`, `Title`)**: Drop records where both `Title` and `Sound Bite Text` are empty or blank, as they contain no semantic payload.
2. **Identifier (`Post ID`)**: Fill missing IDs with deterministically generated SHA256 hashes of the article title/content.
3. **Ghost Columns**: Prune all `Unnamed:*` columns prior to ingestion.

### B. Duplicate Handling
1. Deduplicate records based on `Post ID` or exact content hashes (`Title` + `Sound Bite Text`).
2. Maintain an audit log of deduplicated record counts during preprocessing.

### C. Text Normalization & Noise Cleaning
1. **HTML & Boilerplate Stripping**: Clean occasional HTML tags and trailing website copyright footers (e.g. 'Copyright © 2024-25 DB Corp ltd.').
2. **Whitespace Normalization**: Replace double line breaks (`\r\n`), tabs, and multiple consecutive spaces with standard single spaces.
3. **Unicode & Multi-script Support**: Retain Devanagari (Hindi), Bengali, and English characters without forced ASCII conversion to ensure accurate multilingual search embeddings.

### D. Document Standardization & RAG Readiness
1. **Standard Document Schema**:
   ```json
   {
     "doc_id": "Post ID / Hash",
     "title": "Title",
     "text": "Sound Bite Text",
     "metadata": {
       "source_type": "News",
       "char_length": 1250
     }
   }
   ```
2. **Chunking Threshold**: Target chunk size of 250 - 500 words with 50-word overlap for long news articles.