import os
import re
import sqlite3
import pandas as pd
from typing import Dict, Any, List, Tuple
from pathlib import Path

TAXONOMY_PATH = Path("data/taxonomies/generated_disaster_taxonomy.md")
DB_PATH = Path("data/vector_db/metadata.sqlite")

# Classification label dictionaries
PRIMARY_FRAMES = {
    "F1": "Forecasts, Alerts & Hazard Monitoring",
    "F2": "Risk, Vulnerability & Preparedness Assessment",
    "F3": "Impact, Disruption & Damage",
    "F4": "Emergency Response, Relief & Community Solidarity",
    "F5": "Governance, Policy & Institutional Politics",
    "F6": "Non-Disaster / Metaphorical / Unrelated"
}

CAUSAL_ATTRIBUTIONS = {
    "C1": "Natural / Meteorological Extremes",
    "C2": "Infrastructure / Engineering & Water-Management Failures",
    "C3": "Land-Use, Encroachment & Environmental Degradation",
    "C4": "Administrative / Governance Lapses",
    "C5": "Fatalistic / Divine / Inevitable",
    "C6": "No Explicit Causal Claim / Descriptive"
}

TEMPORAL_PHASES = {
    "T1": "Anticipatory / Pre-Event Preparedness",
    "T2": "Acute Crisis / Ongoing Hazard",
    "T3": "Immediate Aftermath & Relief",
    "T4": "Recovery, Mitigation & Policy (Off-Season)",
    "T5": "No Event-Specific Temporal Anchor / General"
}

STANCE_ACTIONS = {
    "A1": "Accountability & Blame Demands",
    "A2": "Solidarity, Mutual Aid & Community Action",
    "A3": "Resignation, Chronic Vulnerability & Fatalism",
    "A4": "Safety Advisories & Precautionary Directives",
    "A5": "Resilience & Return-to-Normal",
    "A6": "Neutral / Informational Reporting"
}

def classify_record(title: str, content: str, source_type: str, source_dataset: str) -> Dict[str, str]:
    text = f"{title or ''} {content or ''}".lower()
    
    # 1. Primary Communicative Frame (dim_primary_frame: F1 - F6)
    if any(k in text for k in ["forecast", "alert", "imd", "warning", "bulletin", "in spate", "danger mark", "warning level", "heavy rain alert", "yellow alert", "orange alert", "red alert"]):
        frame = "F1"
    elif any(k in text for k in ["rescue", "relief", "sdrf", "ndrf", "evacuat", "camp", "food packet", "ex-gratia", "ex gratia", "compensation", "volunteer", "solidarity", "boat deployed", "ration"]):
        frame = "F4"
    elif any(k in text for k in ["inundat", "submerg", "marooned", "death toll", "casualties", "displaced", "crore loss", "damaged", "washed away", "landslide blocked", "waterlog", "breach"]):
        frame = "F3"
    elif any(k in text for k in ["preparedness", "mock drill", "vulnerab", "hazard map", "risk assessment", "early warning system", "readiness"]):
        frame = "F2"
    elif any(k in text for k in ["government", "minister", "cabinet", "budget", "tribunal", "ngt", "dam management", "embankment project", "inter-state", "censure", "policy", "negligence", "corruption"]):
        frame = "F5"
    elif not any(k in text for k in ["flood", "rain", "disaster", "water", "river", "landslide", "cyclone", "storm"]):
        frame = "F6"
    else:
        frame = "F3" # default flood impact framing for disaster texts

    # 2. Causal Attribution (dim_causal_attribution: C1 - C6)
    if any(k in text for k in ["dam release", "barrage gate", "embankment breach", "dyke breach", "pump failure", "drainage failure", "culvert"]):
        causal = "C2"
    elif any(k in text for k in ["encroachment", "illegal construction", "wetland", "deforestation", "sand mining", "unplanned urban"]):
        causal = "C3"
    elif any(k in text for k in ["negligence", "corruption", "inaction", "delayed response", "poor governance", "failure of administration", "scam"]):
        causal = "C4"
    elif any(k in text for k in ["cloudburst", "heavy downpour", "torrential rain", "monsoon surge", "incessant rain", "upstream rainfall", "cyclone", "depression"]):
        causal = "C1"
    elif any(k in text for k in ["nature's wrath", "act of god", "kismat", "fate", "destiny"]):
        causal = "C5"
    else:
        causal = "C6"

    # 3. Temporal Phase (dim_temporal_phase: T1 - T5)
    if frame == "F1" or any(k in text for k in ["forecast", "expected", "likely to hit", "advise to evacuate", "precaution", "ahead of"]):
        temporal = "T1"
    elif any(k in text for k in ["underway", "ongoing", "continues to inundate", "currently submerged", "live update", "marooned now", "rising"]):
        temporal = "T2"
    elif any(k in text for k in ["aftermath", "tallying loss", "relief distribution", "compensation announced", "restoration", "retreating", "subsided"]):
        temporal = "T3"
    elif frame == "F5" or any(k in text for k in ["long-term", "reconstruction", "mitigation plan", "master plan", "budget allocation", "next season"]):
        temporal = "T4"
    else:
        temporal = "T2" if frame in ("F3", "F4") else "T5"

    # 4. Stance / Action Demands (dim_stance_action: A1 - A6)
    stances = []
    if any(k in text for k in ["demand", "probe", "inquiry", "resign", "shame", "action against", "negligent", "who is responsible", "accountability"]):
        stances.append("A1")
    if any(k in text for k in ["volunteer", "helping", "solidarity", "mutual aid", "together", "community support", "brave", "salute"]):
        stances.append("A2")
    if any(k in text for k in ["every year", "nothing will change", "helpless", "fate", "suffering again", "routine misery"]):
        stances.append("A3")
    if any(k in text for k in ["stay indoors", "avoid low-lying", "helpline", "evacuate immediately", "do not venture", "safety advisory"]):
        stances.append("A4")
    if any(k in text for k in ["limping back", "normalcy", "restored", "resilience", "reopened"]):
        stances.append("A5")
    
    if not stances:
        stances.append("A6")

    primary_stance = stances[0]

    return {
        "dim_primary_frame": frame,
        "dim_primary_frame_label": PRIMARY_FRAMES.get(frame, "Unknown"),
        "dim_causal_attribution": causal,
        "dim_causal_attribution_label": CAUSAL_ATTRIBUTIONS.get(causal, "Unknown"),
        "dim_temporal_phase": temporal,
        "dim_temporal_phase_label": TEMPORAL_PHASES.get(temporal, "Unknown"),
        "dim_stance_action": primary_stance,
        "dim_stance_action_label": STANCE_ACTIONS.get(primary_stance, "Unknown"),
        "all_stances": ",".join(stances)
    }

def run_classification_pipeline(sample_size: int = 2500):
    print(f"=== RUNNING TAXONOMY CLASSIFICATION PIPELINE ON SAMPLE (N = {sample_size}) ===")
    conn = sqlite3.connect(DB_PATH)
    
    # Stratified sampling across both datasets (News: ~1800, Reddit: ~700)
    query_news = f"""
        SELECT vector_id, source_dataset, title, content, source_type
        FROM chunk_metadata
        WHERE source_dataset = 'master_news_corpus'
        ORDER BY RANDOM()
        LIMIT {int(sample_size * 0.72)}
    """
    query_reddit = f"""
        SELECT vector_id, source_dataset, title, content, source_type
        FROM chunk_metadata
        WHERE source_dataset = 'sagar_reddit_dataset'
        ORDER BY RANDOM()
        LIMIT {int(sample_size * 0.28)}
    """
    
    df_news = pd.read_sql_query(query_news, conn)
    df_reddit = pd.read_sql_query(query_reddit, conn)
    df_sample = pd.concat([df_news, df_reddit], ignore_index=True)
    print(f"Sample loaded: Total {len(df_sample)} rows ({len(df_news)} news + {len(df_reddit)} Reddit)")

    records_to_insert = []
    for idx, row in df_sample.iterrows():
        tags = classify_record(
            title=row["title"],
            content=row["content"],
            source_type=row["source_type"],
            source_dataset=row["source_dataset"]
        )
        records_to_insert.append({
            "vector_id": row["vector_id"],
            "source_dataset": row["source_dataset"],
            "title": row["title"],
            "content_snippet": (row["content"][:200] + "...") if len(row["content"] or "") > 200 else row["content"],
            "dim_primary_frame": tags["dim_primary_frame"],
            "dim_primary_frame_label": tags["dim_primary_frame_label"],
            "dim_causal_attribution": tags["dim_causal_attribution"],
            "dim_causal_attribution_label": tags["dim_causal_attribution_label"],
            "dim_temporal_phase": tags["dim_temporal_phase"],
            "dim_temporal_phase_label": tags["dim_temporal_phase_label"],
            "dim_stance_action": tags["dim_stance_action"],
            "dim_stance_action_label": tags["dim_stance_action_label"],
            "all_stances": tags["all_stances"]
        })

    df_tagged = pd.DataFrame(records_to_insert)

    # Save to SQLite table in metadata.sqlite
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS sample_taxonomy_classifications;")
    cursor.execute("""
        CREATE TABLE sample_taxonomy_classifications (
            vector_id INTEGER PRIMARY KEY,
            source_dataset TEXT,
            title TEXT,
            content_snippet TEXT,
            dim_primary_frame TEXT,
            dim_primary_frame_label TEXT,
            dim_causal_attribution TEXT,
            dim_causal_attribution_label TEXT,
            dim_temporal_phase TEXT,
            dim_temporal_phase_label TEXT,
            dim_stance_action TEXT,
            dim_stance_action_label TEXT,
            all_stances TEXT
        );
    """)
    conn.commit()

    df_tagged.to_sql("sample_taxonomy_classifications", conn, if_exists="append", index=False)
    print("Successfully populated table `sample_taxonomy_classifications`.")

    # Execute SQL Aggregation Queries for statistical reporting
    print("\n" + "="*80)
    print(f"SAMPLE STATISTICAL AGGREGATION RESULTS (N = {len(df_tagged)} records)")
    print("="*80)

    # 1. Primary Frame Breakdown
    q_frame = """
        SELECT dim_primary_frame as Code, dim_primary_frame_label as Frame,
               COUNT(*) as Count,
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM sample_taxonomy_classifications), 2) as Percentage
        FROM sample_taxonomy_classifications
        GROUP BY dim_primary_frame, dim_primary_frame_label
        ORDER BY Count DESC;
    """
    df_res_frame = pd.read_sql_query(q_frame, conn)
    print("\n--- 1. Primary Communicative Frame Breakdown ---")
    print(df_res_frame.to_string(index=False))

    # 2. Primary Frame by Dataset Split
    q_frame_ds = """
        SELECT source_dataset as Dataset, dim_primary_frame_label as Frame,
               COUNT(*) as Count
        FROM sample_taxonomy_classifications
        GROUP BY source_dataset, dim_primary_frame_label
        ORDER BY source_dataset, Count DESC;
    """
    df_res_frame_ds = pd.read_sql_query(q_frame_ds, conn)
    print("\n--- 2. Primary Frame by Dataset Split ---")
    print(df_res_frame_ds.to_string(index=False))

    # 3. Causal Attribution Breakdown
    q_causal = """
        SELECT dim_causal_attribution as Code, dim_causal_attribution_label as Attribution,
               COUNT(*) as Count,
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM sample_taxonomy_classifications), 2) as Percentage
        FROM sample_taxonomy_classifications
        GROUP BY dim_causal_attribution, dim_causal_attribution_label
        ORDER BY Count DESC;
    """
    df_res_causal = pd.read_sql_query(q_causal, conn)
    print("\n--- 3. Causal Attribution Breakdown ---")
    print(df_res_causal.to_string(index=False))

    # 4. Temporal Phase Breakdown
    q_temp = """
        SELECT dim_temporal_phase as Code, dim_temporal_phase_label as Phase,
               COUNT(*) as Count,
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM sample_taxonomy_classifications), 2) as Percentage
        FROM sample_taxonomy_classifications
        GROUP BY dim_temporal_phase, dim_temporal_phase_label
        ORDER BY Count DESC;
    """
    df_res_temp = pd.read_sql_query(q_temp, conn)
    print("\n--- 4. Temporal Phase Breakdown ---")
    print(df_res_temp.to_string(index=False))

    # 5. Public Stance Breakdown
    q_stance = """
        SELECT dim_stance_action as Code, dim_stance_action_label as Stance,
               COUNT(*) as Count,
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM sample_taxonomy_classifications), 2) as Percentage
        FROM sample_taxonomy_classifications
        GROUP BY dim_stance_action, dim_stance_action_label
        ORDER BY Count DESC;
    """
    df_res_stance = pd.read_sql_query(q_stance, conn)
    print("\n--- 5. Public Stance & Action Demands Breakdown ---")
    print(df_res_stance.to_string(index=False))

    def format_md_table(df: pd.DataFrame) -> str:
        headers = list(df.columns)
        lines = []
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for _, row in df.iterrows():
            row_str = [str(row[h]) for h in headers]
            lines.append("| " + " | ".join(row_str) + " |")
        return "\n".join(lines)

    # Save summary artifact
    os.makedirs("data/taxonomies", exist_ok=True)
    output_report = Path("data/taxonomies/sample_classification_results.md")
    with open(output_report, "w", encoding="utf-8") as f:
        f.write("# VARTA Sample Taxonomy Classification & Statistical Aggregation Report\n\n")
        f.write(f"**Sample Size (N):** {len(df_tagged)} records  \n")
        f.write(f"**Datasets Included:** `master_news_corpus` ({len(df_news)} records), `sagar_reddit_dataset` ({len(df_reddit)} records)  \n")
        f.write(f"**Storage Table:** SQLite `sample_taxonomy_classifications` in `metadata.sqlite`  \n\n")
        f.write("> [!NOTE]\n> This classification and statistical distribution is based on a representative stratified sample (N = 2,500) to demonstrate the automated classification mechanism. It is not an enumeration of the entire corpus.\n\n")
        
        f.write("## 1. Primary Communicative Frame (`dim_primary_frame`)\n\n")
        f.write(format_md_table(df_res_frame))
        f.write("\n\n## 2. Causal Attribution (`dim_causal_attribution`)\n\n")
        f.write(format_md_table(df_res_causal))
        f.write("\n\n## 3. Temporal Phase (`dim_temporal_phase`)\n\n")
        f.write(format_md_table(df_res_temp))
        f.write("\n\n## 4. Public Stance & Action Demands (`dim_stance_action`)\n\n")
        f.write(format_md_table(df_res_stance))
        f.write("\n\n## 5. Dataset Cross-Tabulation (Primary Frame by Dataset)\n\n")
        f.write(format_md_table(df_res_frame_ds))
        f.write("\n")

    print(f"\n[SUCCESS] Sample report written to {output_report}")
    conn.close()

if __name__ == "__main__":
    run_classification_pipeline(sample_size=2500)
