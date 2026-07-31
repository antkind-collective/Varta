# VARTA - Data Dictionary

## 1. Document Overview & Purpose
This Data Dictionary provides a complete, dataset-derived specification of every detected column in the workspace dataset (`Flood Regional News 25-26 - Sheet1.csv`).
It outlines each column's inferred business purpose, data type, statistical completeness, category, and recommendation for downstream processing (Sprint 1.2+).

> [!NOTE]
> This document is derived purely from dynamic dataset analysis and does not execute or apply any data modifications or preprocessing.

## 2. Complete Data Dictionary Inventory
| Column Name | Inferred Category | Data Type | Completeness (%) | Unique Count | Inferred Purpose | Downstream Recommendation |
| :--- | :--- | :--- | :-: | :-: | :--- | :--- |
| `Post ID` | **Identifier** | `str` | 99.99% | 36,666 | Unique URL / primary key reference for tracking original web news post. | Preserve intact as metadata payload (`doc_id` / `source_url`). |
| `Sound Bite Text` | **Text** | `str` | 99.99% | 32,840 | Main body content / excerpt of news articles covering regional flood events. | Primary Vector Payload. Clean, normalize whitespace, chunk, and embed. |
| `Title` | **Text** | `str` | 99.97% | 29,769 | Headline title summarizing news post or report. | Primary Vector Payload / Context Header. Embed alongside text body. |
| `Source Type` | **Metadata** | `str` | 99.97% | 3 | Categorical metadata label indicating publishing source type (e.g. News). | Preserve intact as structured metadata filter tag. |
| `Unnamed: 4` | **Text** | `str` | 0.01% | 1 | Article image URL media link associated with Consumer Reviews posts (un-named header col 4). | Rename to `Image_URL` in Sprint 1.2 and preserve as optional payload metadata. |
| `Unnamed: 5` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 5). | Drop column completely during data ingestion. |
| `Unnamed: 6` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 6). | Drop column completely during data ingestion. |
| `Unnamed: 7` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 7). | Drop column completely during data ingestion. |
| `Unnamed: 8` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 8). | Drop column completely during data ingestion. |
| `Unnamed: 9` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 9). | Drop column completely during data ingestion. |
| `Unnamed: 10` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 10). | Drop column completely during data ingestion. |
| `Unnamed: 11` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 11). | Drop column completely during data ingestion. |
| `Unnamed: 12` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 12). | Drop column completely during data ingestion. |
| `Unnamed: 13` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 13). | Drop column completely during data ingestion. |
| `Unnamed: 14` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 14). | Drop column completely during data ingestion. |
| `Unnamed: 15` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 15). | Drop column completely during data ingestion. |
| `Unnamed: 16` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 16). | Drop column completely during data ingestion. |
| `Unnamed: 17` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 17). | Drop column completely during data ingestion. |
| `Unnamed: 18` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 18). | Drop column completely during data ingestion. |
| `Unnamed: 19` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 19). | Drop column completely during data ingestion. |
| `Unnamed: 20` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 20). | Drop column completely during data ingestion. |
| `Unnamed: 21` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 21). | Drop column completely during data ingestion. |
| `Unnamed: 22` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 22). | Drop column completely during data ingestion. |
| `Unnamed: 23` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 23). | Drop column completely during data ingestion. |
| `Unnamed: 24` | **Other** | `float64` | 0.0% | 0 | Empty ghost column created by trailing CSV delimiter commas (Unnamed: 24). | Drop column completely during data ingestion. |
| `Unnamed: 25` | **Categorical** | `float64` | 0.01% | 1 | Numerical user rating score (5.0) associated with Consumer Reviews posts (un-named header col 25). | Rename to `User_Rating` in Sprint 1.2 and preserve as optional payload metadata. |
| `Unnamed: 26` | **Categorical** | `str` | 2.18% | 140 | Category / Industry topic taxonomy tag (e.g. Technology | Social Media) present on 799 rows (un-named header col 26). | Rename to `Category_Taxonomy` in Sprint 1.2 and preserve as structured metadata filter tag. |

## 3. Detailed Column Specifications

### 3.1 `Post ID`
- **Category**: Identifier
- **Data Type**: String (`str`)
- **Completeness**: 99.99% (0.01% missing)
- **Cardinality**: 36,666 unique entries
- **Inferred Purpose**: Serves as the primary web locator / URL link to the original regional news story.
- **Recommendation**: Retain in vector store metadata to allow end-users to click back to the source story.

### 3.2 `Sound Bite Text`
- **Category**: Text
- **Data Type**: String (`str`)
- **Completeness**: 99.99% (0.01% missing)
- **Average Length**: ~829 characters (max: 11,666 characters)
- **Inferred Purpose**: Contains the main textual report of regional flood incidents, rescue updates, and damage reports.
- **Recommendation**: Use as the core text chunk payload for embedding generation in RAG.

### 3.3 `Title`
- **Category**: Text
- **Data Type**: String (`str`)
- **Completeness**: 99.97% (0.03% missing)
- **Average Length**: ~76 characters
- **Inferred Purpose**: Concise summary headline of the news post.
- **Recommendation**: Prepend to text chunks (`Title: {title}\nBody: {text}`) to enrich semantic context before vector embedding.

### 3.4 `Source Type`
- **Category**: Metadata
- **Data Type**: String (`str`)
- **Completeness**: 99.97% (0.03% missing)
- **Cardinality**: 3 unique categories (e.g. `News`)
- **Inferred Purpose**: Classification of data provider / source platform.
- **Recommendation**: Index as payload metadata for metadata filtering in RAG queries.

### 3.5 Trailing Ghost Columns (`Unnamed: 5` to `Unnamed: 24`)
- **Category**: Other
- **Completeness**: 0.0% (100% missing values)
- **Inferred Purpose**: Artifacts created by trailing CSV delimiter commas in row headers.
- **Recommendation**: Exclude all 20 ghost columns during data loading / preprocessing phase.