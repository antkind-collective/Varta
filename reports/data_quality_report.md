# VARTA — Data Quality Assessment Report

## 1. Quality Overview & Summary Statistics
- **Total Inspected Rows**: `36,669`
- **Total Inspected Columns**: `27`
- **Full Duplicate Rows**: `1` (`0.0%`)
- **Ghost / Unnamed Empty Columns**: `20`

## 2. Missing & Null Values Analysis
| Column Name | Category | Null Count | Empty Strings | Total Missing | Missing % | Quality Risk Level |
| :--- | :--- | :-: | :-: | :-: | :-: | :--- |
| `Post ID` | **Identifier** | 2 | 0 | 2 | 0.01% | 🟡 Low Missingness |
| `Sound Bite Text` | **Text** | 5 | 0 | 5 | 0.01% | 🟡 Low Missingness |
| `Title` | **Text** | 10 | 0 | 10 | 0.03% | 🟡 Low Missingness |
| `Source Type` | **Metadata** | 10 | 0 | 10 | 0.03% | 🟡 Low Missingness |
| `Unnamed: 4` | **Text** | 36,665 | 0 | 36,665 | 99.99% | 🟠 High Missingness |
| `Unnamed: 5` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 6` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 7` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 8` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 9` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 10` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 11` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 12` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 13` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 14` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 15` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 16` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 17` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 18` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 19` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 20` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 21` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 22` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 23` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 24` | **Other** | 36,669 | 0 | 36,669 | 100.0% | 🔴 Critical (Ghost Column) |
| `Unnamed: 25` | **Categorical** | 36,665 | 0 | 36,665 | 99.99% | 🟠 High Missingness |
| `Unnamed: 26` | **Categorical** | 35,870 | 0 | 35,870 | 97.82% | 🟠 High Missingness |

## 3. Duplicate Row & Key Uniqueness Analysis
### Full Row Duplicates
- Exact duplicate records across all columns: **1** (0.0%)

### Primary Key / Identifier Column Duplicates
- Column `Post ID`: **1** duplicates (0.0%)

## 4. Empirical Validation of Overflow Columns (`Unnamed: 4`, `Unnamed: 25`, `Unnamed: 26`)

### A. Root Cause Analysis
Deep row-level inspection of the raw CSV file (`data/Flood Regional News 25-26 - Sheet1.csv`) reveals that the overflow columns **are NOT caused by malformed CSV row parsing, line break corruption, or missing quotes**.
Every row in the CSV file is cleanly delimited with exactly 27 comma-separated field positions. The emergence of `Unnamed: 4`, `Unnamed: 25`, and `Unnamed: 26` is caused by an **incomplete header definition in line 1 of the CSV** (`Post ID,Sound Bite Text,Title,Source Type,,,,,,,,,,,,,,,,,,,,,,,`), which defined names for only the first 4 columns while leaving 23 trailing field positions un-named.

### B. Representative Sample Analysis & Findings

#### 1. `Unnamed: 26` (799 non-null records)
- **Sample Values**: `Technology | Social Media`, `Industry | Airline`, `Finance | General Finance`, `Politics And Society | General Politics And Society`.
- **Nature of Content**: **Genuine dataset metadata**. Contains rich category / industry taxonomy tags for news articles.
- **Downstream Action**: Rename to `Category_Taxonomy` during Sprint 1.2 and preserve as metadata for query filtering.

#### 2. `Unnamed: 4` (4 non-null records)
- **Sample Values**: `https://images.hindustantimes.com/auto/auto-images/default/default-1600x900.jpg`.
- **Nature of Content**: **Genuine dataset metadata**. Contains media image URLs associated with Consumer Reviews posts.
- **Downstream Action**: Rename to `Image_URL` during Sprint 1.2 and preserve as optional metadata.

#### 3. `Unnamed: 25` (4 non-null records)
- **Sample Values**: `5.0`.
- **Nature of Content**: **Genuine dataset metadata**. Contains numerical user rating scores associated with Consumer Reviews posts.
- **Downstream Action**: Rename to `User_Rating` during Sprint 1.2 and preserve as optional metadata.

#### 4. `Unnamed: 5` through `Unnamed: 24` (20 ghost columns, 0 non-null records)
- **Sample Values**: 100% missing (`NaN`) across all 36,669 rows.
- **Nature of Content**: Structural artifacts from trailing delimiter commas in the CSV header.
- **Downstream Action**: Drop all 20 columns during Sprint 1.2 data ingestion.

## 5. Structural Anomalies & Data Integrity Summary
1. **Header Misalignment**: Header row 1 contains 23 un-named trailing comma delimiters, forcing pandas to assign generic `Unnamed:*` labels to fields 4 through 26.
2. **Empty String Records**: Text fields contain occasional empty strings or whitespace-only records that should be treated as missing.
3. **Multi-lingual / Non-ASCII Content**: News articles contain Hindi (Devanagari) and Bengali scripts alongside English news content. Normalization should preserve Unicode formatting to maintain multilingual search capability.