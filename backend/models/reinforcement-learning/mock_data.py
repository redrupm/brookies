import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

def create_mock_parquet(days=100, num_stocks=60):
    """
    Generates a fake dataset mimicking the exact flat schema of the newly fixed 
    prep_data.py script so you can test your environment and agent loop locally.
    """
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    data_dir.mkdir(exist_ok=True) # Ensure the data directory exists
    
    output_path = data_dir / "master_feed.parquet"
    
    print(f"Generating mock data for {num_stocks} stocks over {days} days...")
    
    start_date = datetime(2023, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(days)]
    tickers = [f"TICK{str(i).zfill(3)}" for i in range(num_stocks)]
    
    records = []
    
    for date in dates:
        for ticker in tickers:
            records.append({
                'Date': date,
                'Ticker': ticker,
                'Close': np.random.uniform(10.0, 500.0),
                'norm_price': np.random.uniform(-0.2, 0.2), # +/- 20% from moving avg
                'score': np.random.uniform(0.0, 10.0),
                'confidence': np.random.uniform(0.0, 100.0),
                'direction': np.random.choice([-1, 0, 1])
            })
            
    df = pd.DataFrame(records)
    
    # Sort just like the real data generator
    df = df.sort_values(by=['Date', 'Ticker'])
    
    # Drop duplicates just in case, to guarantee the env sees clean Series
    df = df.drop_duplicates(subset=['Date', 'Ticker'], keep='first')
    
    df.to_parquet(output_path, engine='pyarrow')
    print(f"Successfully saved {len(df)} rows to {output_path}")
    print("You can now safely run training.py!")

if __name__ == "__main__":
    create_mock_parquet()