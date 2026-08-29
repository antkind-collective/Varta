import pandas as pd
from pathlib import Path

csv_files = [
    Path('data/uploads/test_500.csv'),
    Path('data/uploads/test_650_dataset.csv'),
    Path('data/Flood Regional News 25-26 - Sheet1.csv')
]

for p in csv_files:
    if not p.exists():
        continue
    try:
        df = pd.read_csv(p)
        print("=" * 60)
        print(f"File: {p} (Total rows: {len(df)})")
        print(f"Columns: {list(df.columns)}")
        
        # Check reddit matches
        mask = df.astype(str).apply(lambda row: row.str.contains('reddit|chennai rental|typical reddit moment', case=False, regex=True)).any(axis=1)
        matches = df[mask]
        print(f"Matches for 'reddit' / 'chennai rental' / 'typical reddit moment': {len(matches)}")
        if len(matches) > 0:
            for idx, (_, row) in enumerate(matches.head(5).iterrows()):
                title = str(row.get('title', row.get('Title', 'No title')))
                url = str(row.get('url', row.get('source_url', row.get('URL', 'No url'))))
                print(f"  [{idx+1}] Title: {title[:70]} | URL: {url[:70]}")
    except Exception as e:
        print(f"Error reading {p}: {e}")
