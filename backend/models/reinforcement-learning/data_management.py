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
        
        # Extract unique dates to define the simulation timeline
        self.dates = sorted(df['Date'].unique())
        self.max_steps = len(self.dates) - 1
        self.current_step = 0
        
        # --- Extreme Optimization ---
        # Group by Date so we can instantly grab a specific day's data
        self.daily_data = {}
        for date, group in df.groupby('Date'):
            # Store as a dictionary keyed by Ticker for instant row lookups
            group = group.set_index('Ticker')
            self.daily_data[date] = group
            
    def reset(self):
        self.current_step = 0
        
    def is_done(self):
        return self.current_step >= self.max_steps
        
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