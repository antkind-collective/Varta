# VARTA — Dynamic Schema Analysis & Classification Report

## 1. Schema Analysis Overview
Every column in the dataset has been automatically categorized based on data types, value uniqueness, content patterns, and statistical properties.

## 2. Category Distribution Breakdown
| Category | Column Count | Columns | Description |
| :--- | :-: | :--- | :--- |
| **Identifier** | 1 | `Post ID` | Unique keys, URLs, or primary identifiers used for document reference. |
| **Text** | 3 | `Sound Bite Text`, `Title`, `Unnamed: 4` | Free-form text blocks used for semantic embedding, retrieval, and RAG chunking. |
| **Metadata** | 1 | `Source Type` | Structured domain attributes suitable for metadata filtering during RAG queries. |
| **Other** | 20 | `Unnamed: 5`, `Unnamed: 6`, `Unnamed: 7`, `Unnamed: 8`, `Unnamed: 9`, `Unnamed: 10`, `Unnamed: 11`, `Unnamed: 12`, `Unnamed: 13`, `Unnamed: 14`, `Unnamed: 15`, `Unnamed: 16`, `Unnamed: 17`, `Unnamed: 18`, `Unnamed: 19`, `Unnamed: 20`, `Unnamed: 21`, `Unnamed: 22`, `Unnamed: 23`, `Unnamed: 24` | Unnamed, 100% null, or ghost columns created by CSV trailing delimiters. |
| **Categorical** | 2 | `Unnamed: 25`, `Unnamed: 26` | Discrete, low-cardinality fields representing categories or tags. |

## 3. Detailed Column Classification & Rationale
| Column Name | Category | Data Type | Unique Ratio | Classification Rationale |
| :--- | :--- | :--- | :-: | :--- |
| `Post ID` | **Identifier** | `str` | 99.99% | High cardinality (uniqueness ratio: 99.99%) with ID/URL patterns or explicit primary key naming ('Post ID'). |
| `Sound Bite Text` | **Text** | `str` | 89.56% | Free-form textual content with average length of 828.9 characters (max: 11666). Suitable for semantic embedding and chunking. |
| `Title` | **Text** | `str` | 81.18% | Free-form textual content with average length of 76.4 characters (max: 340). Suitable for semantic embedding and chunking. |
| `Source Type` | **Metadata** | `str` | 0.01% | Low cardinality discrete set (3 unique values across 36669 rows). Functions as domain metadata. |
| `Unnamed: 4` | **Text** | `str` | 0.00% | Free-form textual content with average length of 79.0 characters (max: 79). Suitable for semantic embedding and chunking. |
| `Unnamed: 5` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 6` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 7` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 8` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 9` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 10` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 11` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 12` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 13` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 14` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 15` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 16` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 17` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 18` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 19` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 20` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 21` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 22` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 23` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 24` | **Other** | `float64` | 0.00% | Column contains 100% missing / null values across all rows. |
| `Unnamed: 25` | **Categorical** | `float64` | 0.00% | Numeric data type with low unique value count (1 unique values), acting as a categorical code/status. |
| `Unnamed: 26` | **Categorical** | `str` | 0.38% | Low cardinality discrete set (140 unique values across 36669 rows). Functions as categorical field. |

## 4. Semantic Search Suitability Assessment
- **Primary Vector Content**: `Sound Bite Text` (Main article text) and `Title` (Article headline). Combining headline + body yields optimal context embeddings.
- **Primary Document ID**: `Post ID` (URL / Unique string hash).
- **Metadata Filters**: `Source Type` (Source category filter).
- **Fields to Drop**: All empty `Unnamed:*` ghost columns.