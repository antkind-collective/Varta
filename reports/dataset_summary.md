# VARTA — Dataset Summary Report

## 1. Executive Overview
- **Dataset File**: `Flood Regional News 25-26 - Sheet1.csv`
- **File Path**: `C:\Users\binda\OneDrive\Desktop\Varta\data\Flood Regional News 25-26 - Sheet1.csv`
- **File Size**: `37.48 MB` (`39303418 bytes`)
- **Memory Usage in RAM**: `62.41 MB` (`65442649 bytes`)
- **Total Rows**: `36,669`
- **Total Columns**: `27`

## 2. High-Level Dataset Metrics
| Metric | Value | Notes |
| :--- | :--- | :--- |
| Total Records | 36,669 | Total rows present in CSV |
| Total Features/Columns | 27 | Includes valid fields and ghost columns |
| Memory Consumption | 62.41 MB | Deep memory usage loaded into pandas |
| Duplicate Rows | 1 (0.0%) | Exact duplicate rows across all fields |
| Unnamed Ghost Columns | 20 | Trailing empty columns from CSV parsing |

## 3. Structural Column Inventory
| # | Column Name | Data Type | Category | Unique Values | Missing % |
| :-: | :--- | :--- | :--- | :-: | :-: |
| 1 | `Post ID` | `str` | **Identifier** | 36,666 | 0.01% |
| 2 | `Sound Bite Text` | `str` | **Text** | 32,840 | 0.01% |
| 3 | `Title` | `str` | **Text** | 29,769 | 0.03% |
| 4 | `Source Type` | `str` | **Metadata** | 3 | 0.03% |
| 5 | `Unnamed: 4` | `str` | **Text** | 1 | 99.99% |
| 6 | `Unnamed: 5` | `float64` | **Other** | 0 | 100.0% |
| 7 | `Unnamed: 6` | `float64` | **Other** | 0 | 100.0% |
| 8 | `Unnamed: 7` | `float64` | **Other** | 0 | 100.0% |
| 9 | `Unnamed: 8` | `float64` | **Other** | 0 | 100.0% |
| 10 | `Unnamed: 9` | `float64` | **Other** | 0 | 100.0% |
| 11 | `Unnamed: 10` | `float64` | **Other** | 0 | 100.0% |
| 12 | `Unnamed: 11` | `float64` | **Other** | 0 | 100.0% |
| 13 | `Unnamed: 12` | `float64` | **Other** | 0 | 100.0% |
| 14 | `Unnamed: 13` | `float64` | **Other** | 0 | 100.0% |
| 15 | `Unnamed: 14` | `float64` | **Other** | 0 | 100.0% |
| 16 | `Unnamed: 15` | `float64` | **Other** | 0 | 100.0% |
| 17 | `Unnamed: 16` | `float64` | **Other** | 0 | 100.0% |
| 18 | `Unnamed: 17` | `float64` | **Other** | 0 | 100.0% |
| 19 | `Unnamed: 18` | `float64` | **Other** | 0 | 100.0% |
| 20 | `Unnamed: 19` | `float64` | **Other** | 0 | 100.0% |
| 21 | `Unnamed: 20` | `float64` | **Other** | 0 | 100.0% |
| 22 | `Unnamed: 21` | `float64` | **Other** | 0 | 100.0% |
| 23 | `Unnamed: 22` | `float64` | **Other** | 0 | 100.0% |
| 24 | `Unnamed: 23` | `float64` | **Other** | 0 | 100.0% |
| 25 | `Unnamed: 24` | `float64` | **Other** | 0 | 100.0% |
| 26 | `Unnamed: 25` | `float64` | **Categorical** | 1 | 99.99% |
| 27 | `Unnamed: 26` | `str` | **Categorical** | 140 | 97.82% |

## 4. Key Discovery Takeaways
1. **Core Content Columns**: The dataset contains news article entries with rich text titles and body text (`Sound Bite Text`, `Title`), which form the core data source for semantic search.
2. **Primary Identifiers**: `Post ID` acts as a unique URL/identifier for news posts, enabling traceability.
3. **Metadata & Categories**: `Source Type` provides high-level categorisation (e.g. News).
4. **Ghost Columns**: Multiple trailing unnamed columns exist due to trailing delimiter commas in the raw CSV, which should be pruned in preprocessing.