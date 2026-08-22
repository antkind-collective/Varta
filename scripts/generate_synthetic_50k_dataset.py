import os
import random
import pandas as pd
import numpy as np

def generate_synthetic_50k_dataset():
    random.seed(42)
    np.random.seed(42)
    
    target_count = 50000
    output_path = os.path.abspath("data/uploads/synthetic_50k_stress_dataset.csv")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"Generating synthetic 50,000-record stress test dataset at: {output_path}")

    # Vocabulary & Template Generators
    geographies = ["Assam", "Uttar Pradesh", "UP", "Bihar", "West Bengal", "Bengal", "Kerala", "Delhi", "Mumbai", "Odisha", "Gujarat", "Uttarakhand"]
    disaster_terms = ["flood", "floods", "waterlogging", "embankment breach", "heavy rainfall", "inundation", "relief camp", "NDRF rescue", "submerged village", "river overflow", "flood damage"]
    disaster_hindi = ["बाढ़", "जलभराव", "तटबंध दरार", "भारी बारिश", "राहत शिविर", "एनडीआरएफ बचाव अभियान", "नदी का जलस्तर"]
    
    non_disaster_topics = [
        ("India vs Australia Test Match Series Score Updates", "Cricket team captain hits brilliant century in second innings as fans celebrate at Stadium."),
        ("Bollywood Movie Box Office Collection Day 1", "New blockbuster release breaks opening day records across multiplexes nationwide."),
        ("Sensex Rallies 500 Points Driven by IT & Banking Stocks", "Stock market indices registered strong gains following quarterly corporate earnings."),
        ("Latest Smartphone Launch with AI Camera Features", "Tech giant unveils flagship mobile device with 100x zoom and OLED display."),
        ("State Election Results Declaration & Party Campaign Update", "Political leaders address supporters following final election commission counting updates.")
    ]

    source_types = ["News", "Twitter", "Blog", "Official", "Government", None]
    
    records = []

    for i in range(1, target_count + 1):
        # 1. Determine Category Type
        rand_val = random.random()
        
        # Malformed / empty edge cases (~0.5%)
        if rand_val < 0.005:
            post_id = f"SYNTH_50K_{i:05d}"
            title = ""
            text = ""
            source = random.choice(source_types)
            category = "Invalid"
        
        # Completely Irrelevant / Out-of-Domain (~4.5%)
        elif rand_val < 0.05:
            post_id = f"SYNTH_50K_{i:05d}"
            title_tmpl, text_tmpl = random.choice(non_disaster_topics)
            title = f"{title_tmpl} #{i}"
            text = f"{text_tmpl} Additional commentary on market trends and entertainment updates."
            source = random.choice(["News", "Blog", "Twitter"])
            category = "Non-Disaster / Entertainment / Sports"

        # General / Ambiguous Regional News (~35%)
        elif rand_val < 0.40:
            post_id = f"SYNTH_50K_{i:05d}"
            geo = random.choice(geographies)
            title = f"Regional News Update from {geo} Region #{i}"
            text = f"Local administration in {geo} announced new infrastructure development projects. Traffic restrictions updated for city roads."
            source = random.choice(source_types)
            category = "Regional General News"

        # Relevant Flood & Disaster Context (~60%)
        else:
            post_id = f"SYNTH_50K_{i:05d}"
            geo = random.choice(geographies)
            
            # Mix English and Hindi disaster news
            if random.random() < 0.25:
                d_hindi = random.choice(disaster_hindi)
                title = f"{geo} में {d_hindi} से स्थिति गंभीर #{i}"
                text = f"{geo} जिले में {d_hindi} की वजह से कई गांव प्रभावित हुए हैं। जिला प्रशासन द्वारा {random.choice(disaster_hindi)} शुरू किया गया है।"
            else:
                d_term = random.choice(disaster_terms)
                title = f"Severe {d_term} reported in {geo} district #{i}"
                text = f"Continuous heavy rainfall triggered severe {d_term} across multiple villages in {geo}. NDRF teams deployed for rescue operations and relief material distribution."
            
            source = random.choice(["News", "Official", "Government", "Twitter"])
            category = "Disaster / Flood"

        # Duplicate Post ID test (~1% deliberate duplicate IDs to test deduplication)
        if random.random() < 0.01 and i > 10:
            post_id = f"SYNTH_50K_{random.randint(1, i-1):05d}"

        # Image URL / missing URL
        image_url = f"https://images.varta-disaster.org/photo_{i}.jpg" if random.random() > 0.3 else None

        records.append({
            "Post ID": post_id,
            "Sound Bite Text": text,
            "Title": title,
            "Source Type": source,
            "Unnamed: 4": image_url,
            "Unnamed: 25": random.choice([4.5, 3.8, 5.0, None]),
            "Unnamed: 26": category
        })

    df_synth = pd.DataFrame(records)
    df_synth.to_csv(output_path, index=False, encoding="utf-8")
    
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Synthetic 50,000-record dataset generated successfully ({len(df_synth)} rows, {file_size_mb:.2f} MB).")
    return output_path

if __name__ == "__main__":
    generate_synthetic_50k_dataset()
