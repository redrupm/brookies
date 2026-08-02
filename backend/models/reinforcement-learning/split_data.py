import pandas as pd
from constants import *


df = pd.read_parquet(DATA_DIR + "master_feed.parquet")
        
# --- FIX: Clean up yfinance MultiIndex columns ---
# Newer yfinance versions output tuples (e.g., ('Close', 'AAPL')) which 
# Parquet saves as messy strings. We force them back to clean names.
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

df = df.rename(columns=col_map)

# If Date was saved as the index, pull it out into a column
if 'Date' not in df.columns and (df.index.name == 'Date' or 'Date' in df.index.names):
    df = df.reset_index()

# Strict validation checkpoint
if 'Date' not in df.columns or 'Ticker' not in df.columns:
    raise ValueError(f"CRITICAL: Failed to parse 'Date' or 'Ticker'. Available columns: {df.columns.tolist()}")
    
initial_len = len(df)
df = df.drop_duplicates(subset=['Date', 'Ticker'], keep='first')
if len(df) < initial_len:
    print(f"Cleaned {initial_len - len(df)} duplicate rows from the dataset.")

# Extract unique dates to define the simulation timeline
dates = sorted(df['Date'].unique())
cutoff = dates[int(len(dates) * 0.8)]

training = df[df['Date'] < cutoff]
testing = df[df['Date'] > cutoff]

training.to_parquet(DATA_DIR + "training_feed.parquet", engine='pyarrow')
testing.to_parquet(DATA_DIR + "testing_feed.parquet", engine='pyarrow')
