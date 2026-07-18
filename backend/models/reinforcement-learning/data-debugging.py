import pandas as pd
from pathlib import Path

def inspect_data():
    base_dir = Path(__file__).resolve().parent
    parquet_path = base_dir / "data" / "master_feed.parquet"
    
    print(f"Loading {parquet_path}...\n")
    
    try:
        df = pd.read_parquet(parquet_path)
    except Exception as e:
        print(f"Failed to load parquet: {e}")
        return

    print("--- 1. RAW COLUMNS ---")
    print(f"Type: {type(df.columns)}")
    print(f"Values: {df.columns.tolist()}\n")
    
    print("--- 2. RAW INDEX ---")
    print(f"Type: {type(df.index)}")
    print(f"Names: {df.index.names}\n")
    
    print("--- 3. TEST RENAME LOGIC ---")
    col_map = {}
    for col in df.columns:
        col_str = str(col).lower()
        if 'date' in col_str: col_map[col] = 'Date'
        elif 'ticker' in col_str: col_map[col] = 'Ticker'
        elif 'close' in col_str: col_map[col] = 'Close'
        elif 'norm_price' in col_str: col_map[col] = 'norm_price'
        elif 'score' in col_str: col_map[col] = 'score'
        elif 'confidence' in col_str: col_map[col] = 'confidence'
        elif 'direction' in col_str: col_map[col] = 'direction'
        else: col_map[col] = f"UNKNOWN_{col}"
        
    print(f"Mapped Columns: {col_map}")
    
    test_df = df.rename(columns=col_map)
    print(f"\nColumns after rename: {test_df.columns.tolist()}")
    
    print("\n--- 4. DATAFRAME INFO ---")
    test_df.info()

if __name__ == "__main__":
    inspect_data()