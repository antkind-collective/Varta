# VARTA — Data Cleaning Statistics Report (Sprint 1.2)

## 1. Executive Summary Table
| Metric | Raw Dataset | Processed Dataset | Net Change |
| :--- | :-: | :-: | :-: |
| **Total Rows / Records** | 36,669 | 33,975 | -2,694 rows |
| **Total Columns / Features** | 27 | 7 | -20 ghost cols |
| **File Size (Disk)** | 37.48 MB | 34.56 MB | Optimized |

## 2. Quantitative Processing Metrics
| Cleaning Phase | Quantity | Description |
| :--- | :-: | :--- |
| **Ghost Columns Dropped** | 20 | Confirmed empty trailing comma columns (`Unnamed: 5`..`24`) |
| **Columns Renamed** | 7 | Mapped raw header names to clean `snake_case` names |
| **Invalid Payload Rows Filtered** | 5 | Rows missing both `title` and `text_content` payload |
| **Missing Identifiers Hash-Filled** | 0 | SHA256 content hashes generated for missing `post_id` entries |
| **Full Exact Duplicate Rows Removed** | 0 | Identical rows across all fields |
| **Primary Key ID Duplicates Removed** | 1 | Duplicate `post_id` records (kept first) |
| **Content Hash Duplicates Removed** | 2,688 | Duplicate `title` + `text_content` payload hashes |
| **Total Deduplicated Records Removed** | 2,689 | Combined deduplication total |

## 3. Text Normalization Summary
| Column Name | Records Inspected | Records Modified | Modification % |
| :--- | :-: | :-: | :-: |
| `title` | 36,664 | 85 | 0.23% |
| `text_content` | 36,664 | 5,474 | 14.93% |

## 4. Final Processed Column Schema
| Column Index | Field Name | Strategic Role in RAG Pipeline | Data Type |
| :-: | :--- | :--- | :--- |
| 1 | `post_id` | 🔑 Primary Document Reference (`doc_id` / `source_url`) | `object / string` |
| 2 | `text_content` | 🎯 Core Vector Payload | `object / string` |
| 3 | `title` | 🎯 Core Vector Payload | `object / string` |
| 4 | `source_type` | 🏷️ Metadata Filter Attribute | `object / string` |
| 5 | `image_url` | ℹ️ Optional Metadata Attribute | `object / string` |
| 6 | `user_rating` | ℹ️ Optional Metadata Attribute | `object / string` |
| 7 | `category_taxonomy` | 🏷️ Metadata Filter Attribute | `object / string` |