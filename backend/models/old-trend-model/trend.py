import torch
import torch.nn as nn
import yfinance as yf
import numpy as np
import pandas as pd
import time
import logging
import sys
from io import StringIO
import requests

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# --- 1. MODEL DEFINITION ---

class StockPredictor(nn.Module):
    def __init__(self, input_dim, hidden_dim, num_layers, output_dim):
        super().__init__()
        # Ensure dropout matches your training script (0.2)
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        out, (h_n, c_n) = self.lstm(x)
        return self.fc(h_n[-1, :, :])

model = None

SYMBOL_ALIASES = {
    "TWX": "WBD",
}


def _resolve_symbol(symbol: str) -> str:
    return SYMBOL_ALIASES.get(symbol, symbol)


def _fetch_stooq_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    try:
        period_days = {
            "1d": 1,
            "5d": 5,
            "1mo": 31,
            "6mo": 183,
            "1y": 366,
        }.get(period, 366)

        stooq = f"{symbol.lower()}.us"
        response = requests.get(f"https://stooq.com/q/d/l/?s={stooq}&i=d", timeout=10)
        response.raise_for_status()

        frame = pd.read_csv(StringIO(response.text))
        if frame.empty or "Date" not in frame.columns:
            return pd.DataFrame()

        frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
        frame = frame.dropna(subset=["Date"]).sort_values("Date")
        if len(frame) > period_days:
            frame = frame.tail(period_days)

        for col in ["Open", "High", "Low", "Close"]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame = frame.dropna(subset=["Open", "High", "Low", "Close"])

        frame = frame.set_index("Date")
        return frame[["Open", "High", "Low", "Close"]]
    except Exception:
        return pd.DataFrame()


def _fetch_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    lookup_symbol = _resolve_symbol(symbol)

    try:
        df = yf.download(
            tickers=lookup_symbol,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
            timeout=10,
        )
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
    except Exception:
        pass

    ticker = yf.Ticker(lookup_symbol)
    for attempt in range(2):
        try:
            df = ticker.history(period=period)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df
        except Exception:
            if attempt == 0:
                time.sleep(0.35)

    stooq_df = _fetch_stooq_history(lookup_symbol, period=period)
    if not stooq_df.empty:
        return stooq_df

    return pd.DataFrame()

def init_predictor(model_path='output/models/stocks_model.pth'):
    global model
    # Older saved checkpoints were created when this module was named `running`.
    # Register a compatibility alias so torch can unpickle those objects.
    sys.modules.setdefault("running", sys.modules[__name__])
    model = torch.load(model_path, map_location=device, weights_only=False)
    model.eval()
    print("Model loaded successfully.")

# --- 2. PIPELINE & INFERENCE ---

def predict_trend(ticker_symbol):
    if model is None:
        raise RuntimeError("EASY FIX: Model not initialized. Call init_predictor() first.")

    print(f"\nFetching recent data for {ticker_symbol}...")
    
    # 1. Fetch 1 year of data to get a robust mean/std for scaling
    df = _fetch_history(ticker_symbol, period="1y")
    if len(df) < 60:
        raise ValueError(f"Not enough data for {ticker_symbol}")

    # Standardize columns
    df.columns = [c.lower() for c in df.columns]
    
    # Calculate rolling MAs
    df['ma_7'] = df['close'].rolling(window=7).mean()
    df['ma_21'] = df['close'].rolling(window=21).mean()
    df = df.dropna()

    # 2. Extract Features (Mimicking training identically)
    clean_df = df[['open', 'high', 'low', 'close', 'ma_7', 'ma_21']]
    raw_prices = clean_df.values.astype(float)
    safe_prices = raw_prices + 1e-10

    log_returns = np.log(safe_prices[1:, :4] / safe_prices[:-1, :4])
    log_returns = np.clip(log_returns, -0.5, 0.5)

    # Calculate dynamic stats for this ticker
    ticker_mean = np.mean(log_returns, axis=0)
    ticker_std = np.std(log_returns, axis=0) + 1e-9
    
    # Normalize
    scaled_log_returns = (log_returns - ticker_mean) / ticker_std
    price_context = np.log10(safe_prices[1:, 3])

    ma_7_dist = ((clean_df['close'] - clean_df['ma_7']) / clean_df['ma_7']).values[1:]
    ma_21_dist = ((clean_df['close'] - clean_df['ma_21']) / clean_df['ma_21']).values[1:]
    ma_7_dist = np.nan_to_num(ma_7_dist)
    ma_21_dist = np.nan_to_num(ma_21_dist)

    combined_features = np.hstack((
        scaled_log_returns, 
        price_context.reshape(-1, 1),
        ma_7_dist.reshape(-1, 1),
        ma_21_dist.reshape(-1, 1)
    ))

    # 3. Slice the last 30 days for the actual prediction sequence
    recent_features = combined_features[-30:]
    
    # Shape it for the LSTM: (Batch=1, SeqLen=30, Features=7)
    input_tensor = torch.tensor(recent_features).float().unsqueeze(0).to(device)

    # 4. Predict
    with torch.no_grad():
        pred_tensor = model(input_tensor)
    
    # Move to CPU and unpack the 3-day array
    raw_predictions = pred_tensor.cpu().numpy()[0] 

    # 5. UN-SCALE THE MATH
    # In training, target index 0 was 'open'. 
    open_mean = ticker_mean[0]
    open_std = ticker_std[0]

    # Revert Z-Score -> Revert Log -> Get Multiplier
    unscaled_log_returns = (raw_predictions * open_std) + open_mean
    price_multipliers = np.exp(unscaled_log_returns)

    # Project the prices
    last_known_open = df['open'].iloc[-1]
    projected_opens = []
    
    current_price = last_known_open
    for m in price_multipliers:
        current_price *= m
        projected_opens.append(current_price)

    # Print a nice summary for the teammates
    print("-" * 30)
    print(f"3-DAY TREND FORECAST: {ticker_symbol.upper()}")
    print("-" * 30)
    print(f"Last Known Open: ${last_known_open:.2f}")
    
    overall_trend = 1.0
    for i, (price, mult) in enumerate(zip(projected_opens, price_multipliers)):
        change_pct = (mult - 1) * 100
        overall_trend *= mult
        print(f"Day {i+1}: ${price:.2f} ({change_pct:+.2f}%)")
    
    total_change_pct = (overall_trend - 1) * 100
    print("-" * 30)
    print(f"Total Projected Move: {total_change_pct:+.2f}%")
    print("-" * 30)

    return projected_opens


def predict_trend_with_current(ticker_symbol):
    """
    Returns trend prediction with the current price.
    Returns a dict with 'projected_opens' and 'current_price'.
    """
    if model is None:
        raise RuntimeError("EASY FIX: Model not initialized. Call init_predictor() first.")

    print(f"\nFetching recent data for {ticker_symbol}...")
    
    # 1. Fetch 1 year of data to get a robust mean/std for scaling
    df = _fetch_history(ticker_symbol, period="1y")
    if len(df) < 60:
        raise ValueError(f"Not enough data for {ticker_symbol}")

    # Standardize columns
    df.columns = [c.lower() for c in df.columns]
    
    # Calculate rolling MAs
    df['ma_7'] = df['close'].rolling(window=7).mean()
    df['ma_21'] = df['close'].rolling(window=21).mean()
    df = df.dropna()

    # 2. Extract Features (Mimicking training identically)
    clean_df = df[['open', 'high', 'low', 'close', 'ma_7', 'ma_21']]
    raw_prices = clean_df.values.astype(float)
    safe_prices = raw_prices + 1e-10

    log_returns = np.log(safe_prices[1:, :4] / safe_prices[:-1, :4])
    log_returns = np.clip(log_returns, -0.5, 0.5)

    # Calculate dynamic stats for this ticker
    ticker_mean = np.mean(log_returns, axis=0)
    ticker_std = np.std(log_returns, axis=0) + 1e-9
    
    # Normalize
    scaled_log_returns = (log_returns - ticker_mean) / ticker_std
    price_context = np.log10(safe_prices[1:, 3])

    ma_7_dist = ((clean_df['close'] - clean_df['ma_7']) / clean_df['ma_7']).values[1:]
    ma_21_dist = ((clean_df['close'] - clean_df['ma_21']) / clean_df['ma_21']).values[1:]
    ma_7_dist = np.nan_to_num(ma_7_dist)
    ma_21_dist = np.nan_to_num(ma_21_dist)

    combined_features = np.hstack((
        scaled_log_returns, 
        price_context.reshape(-1, 1),
        ma_7_dist.reshape(-1, 1),
        ma_21_dist.reshape(-1, 1)
    ))

    # 3. Slice the last 30 days for the actual prediction sequence
    recent_features = combined_features[-30:]
    
    # Shape it for the LSTM: (Batch=1, SeqLen=30, Features=7)
    input_tensor = torch.tensor(recent_features).float().unsqueeze(0).to(device)

    # 4. Predict
    with torch.no_grad():
        pred_tensor = model(input_tensor)
    
    # Move to CPU and unpack the 3-day array
    raw_predictions = pred_tensor.cpu().numpy()[0] 

    # 5. UN-SCALE THE MATH
    # In training, target index 0 was 'open'. 
    open_mean = ticker_mean[0]
    open_std = ticker_std[0]

    # Revert Z-Score -> Revert Log -> Get Multiplier
    unscaled_log_returns = (raw_predictions * open_std) + open_mean
    price_multipliers = np.exp(unscaled_log_returns)

    # Project the prices
    last_known_open = df['open'].iloc[-1]
    projected_opens = []
    
    current_price = last_known_open
    for m in price_multipliers:
        current_price *= m
        projected_opens.append(current_price)

    return {
        'projected_opens': projected_opens,
        'current_price': last_known_open
    }


# --- TEST IT ---
if __name__ == "__main__":
    init_predictor()
    
    # Teammates can now just pass a string!
    predict_trend("MSFT")
    predict_trend("AAPL")