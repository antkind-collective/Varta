# VARTA Sample Taxonomy Classification & Statistical Aggregation Report

**Sample Size (N):** 2500 records  
**Datasets Included:** `master_news_corpus` (1800 records), `sagar_reddit_dataset` (700 records)  
**Storage Table:** SQLite `sample_taxonomy_classifications` in `metadata.sqlite`  

> [!NOTE]
> This classification and statistical distribution is based on a representative stratified sample (N = 2,500) to demonstrate the automated classification mechanism. It is not an enumeration of the entire corpus.

## 1. Primary Communicative Frame (`dim_primary_frame`)

| Code | Frame | Count | Percentage |
| --- | --- | --- | --- |
| F3 | Impact, Disruption & Damage | 912 | 36.48 |
| F4 | Emergency Response, Relief & Community Solidarity | 825 | 33.0 |
| F1 | Forecasts, Alerts & Hazard Monitoring | 420 | 16.8 |
| F5 | Governance, Policy & Institutional Politics | 192 | 7.68 |
| F6 | Non-Disaster / Metaphorical / Unrelated | 118 | 4.72 |
| F2 | Risk, Vulnerability & Preparedness Assessment | 33 | 1.32 |

## 2. Causal Attribution (`dim_causal_attribution`)

| Code | Attribution | Count | Percentage |
| --- | --- | --- | --- |
| C6 | No Explicit Causal Claim / Descriptive | 2102 | 84.08 |
| C1 | Natural / Meteorological Extremes | 284 | 11.36 |
| C3 | Land-Use, Encroachment & Environmental Degradation | 56 | 2.24 |
| C4 | Administrative / Governance Lapses | 36 | 1.44 |
| C2 | Infrastructure / Engineering & Water-Management Failures | 14 | 0.56 |
| C5 | Fatalistic / Divine / Inevitable | 8 | 0.32 |

## 3. Temporal Phase (`dim_temporal_phase`)

| Code | Phase | Count | Percentage |
| --- | --- | --- | --- |
| T2 | Acute Crisis / Ongoing Hazard | 1614 | 64.56 |
| T1 | Anticipatory / Pre-Event Preparedness | 521 | 20.84 |
| T4 | Recovery, Mitigation & Policy (Off-Season) | 195 | 7.8 |
| T5 | No Event-Specific Temporal Anchor / General | 134 | 5.36 |
| T3 | Immediate Aftermath & Relief | 36 | 1.44 |

## 4. Public Stance & Action Demands (`dim_stance_action`)

| Code | Stance | Count | Percentage |
| --- | --- | --- | --- |
| A6 | Neutral / Informational Reporting | 2206 | 88.24 |
| A1 | Accountability & Blame Demands | 132 | 5.28 |
| A2 | Solidarity, Mutual Aid & Community Action | 77 | 3.08 |
| A5 | Resilience & Return-to-Normal | 41 | 1.64 |
| A3 | Resignation, Chronic Vulnerability & Fatalism | 32 | 1.28 |
| A4 | Safety Advisories & Precautionary Directives | 12 | 0.48 |

## 5. Dataset Cross-Tabulation (Primary Frame by Dataset)

| Dataset | Frame | Count |
| --- | --- | --- |
| master_news_corpus | Emergency Response, Relief & Community Solidarity | 692 |
| master_news_corpus | Impact, Disruption & Damage | 532 |
| master_news_corpus | Forecasts, Alerts & Hazard Monitoring | 333 |
| master_news_corpus | Governance, Policy & Institutional Politics | 155 |
| master_news_corpus | Non-Disaster / Metaphorical / Unrelated | 63 |
| master_news_corpus | Risk, Vulnerability & Preparedness Assessment | 25 |
| sagar_reddit_dataset | Impact, Disruption & Damage | 380 |
| sagar_reddit_dataset | Emergency Response, Relief & Community Solidarity | 133 |
| sagar_reddit_dataset | Forecasts, Alerts & Hazard Monitoring | 87 |
| sagar_reddit_dataset | Non-Disaster / Metaphorical / Unrelated | 55 |
| sagar_reddit_dataset | Governance, Policy & Institutional Politics | 37 |
| sagar_reddit_dataset | Risk, Vulnerability & Preparedness Assessment | 8 |
