import pandas as pd
import numpy as np

class StockDataFeed:
    """
    Loads the pre-computed Parquet file into memory and serves O(1) lookups 
    to the DynamicSlotTradingEnv.
    """
    def __init__(self, parquet_path):
        print("Loading Parquet data into RAM...")
        df = pd.read_parquet(parquet_path)
        
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
        self.dates = sorted(df['Date'].unique())
        self.max_steps = len(self.dates) - 1
        
        # --- Extreme Optimization ---
        # Group by Date so we can instantly grab a specific day's data
        self.daily_data = {}
        for date, group in df.groupby('Date'):
            # Store as a dictionary keyed by Ticker for instant row lookups
            group = group.set_index('Ticker')
            self.daily_data[date] = group
        
    def _get_day_df(self, step):
        date = self.dates[step]
        return self.daily_data[date]
    
    def get_features(self, ticker, step):
        """Returns the specific ML features for a ticker on a given step."""
        day_df = self._get_day_df(step)
        
        if ticker in day_df.index:
            row = day_df.loc[ticker]
            return {
                'price': float(row['Close']),
                'norm_price': float(row['norm_price']),
                'score': float(row['score']),
                'confidence': float(row['confidence']),
                'direction': float(row['direction'])
            }
        
        # Fallback if a ticker is halted or missing data on this day
        return {'price': 0.0, 'norm_price': 0.0, 'score': 0.0, 'confidence': 0.0, 'direction': 0.0}

    def get_price(self, ticker, step):
        """Fast helper method just for price lookups during portfolio valuation."""
        day_df = self._get_day_df(step)
        if ticker in day_df.index:
            return float(day_df.loc[ticker, 'Close'])
        return 0.0

    def get_top_screener_stocks(self, step, top_n=50):
        """
        Acts as the dynamic screener. Returns a list of the best ticker 
        symbols for this specific day based on your app.py trend scores.
        """
        day_df = self._get_day_df(step)
        
        # Sort today's universe by the pre-computed 'score' column descending
        best_stocks = day_df.sort_values(by='score', ascending=False)
        
        # Return just the ticker symbols (the index)
        return best_stocks.head(top_n).index.tolist()