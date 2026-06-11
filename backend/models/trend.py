import torch
import torch.nn as nn
import torch.nn.functional as F
import yfinance as yf
import pandas as pd
import numpy as np
import warnings

# Suppress yfinance warnings for a cleaner console
warnings.filterwarnings('ignore')

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# --- 1. MODEL DEFINITION ---

class StockPredictor(nn.Module):
    def __init__(self, input_dim, hidden_dim, num_layers, output_dim):
        super().__init__()
        # Must match the training script perfectly (8 inputs, 128 hidden, 0.4 dropout)
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True, dropout=0.4)
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        out, (h_n, c_n) = self.lstm(x)
        return self.fc(h_n[-1, :, :])

model = None

def init_predictor(model_path='three-day-model.pth'):
    global model
    
    # Initialize the architecture 
    model = StockPredictor(input_dim=8, hidden_dim=128, num_layers=2, output_dim=3).to(device)
    
    # Load the state dict (safer than loading the entire model object)
    state_dict = torch.load(model_path, map_location=device, weights_only=False)
    model.load_state_dict(state_dict)
    
    model.eval()
    print("AI Engine loaded and ready.")

# --- 2. MACRO DATA FETCHER ---

def get_macro_context(as_of: str = None):
    # Fetch ~2 years to ensure we have enough data for the 252-day rolling window
    # If `as_of` is provided, request data ending at that date so context is anchored.
    if as_of:
        spy = yf.download('SPY', period="2y", end=as_of, progress=False)
        vix = yf.download('^VIX', period="2y", end=as_of, progress=False)
    else:
        spy = yf.download('SPY', period="2y", progress=False)
        vix = yf.download('^VIX', period="2y", progress=False)
    
    if isinstance(spy.columns, pd.MultiIndex): spy.columns = spy.columns.get_level_values(0)
    if isinstance(vix.columns, pd.MultiIndex): vix.columns = vix.columns.get_level_values(0)
    
    macro = pd.DataFrame({'spy_close': spy['Close'], 'vix_close': vix['Close']})
    macro['spy_return'] = np.log(macro['spy_close'] / macro['spy_close'].shift(1))
    
    macro['spy_z'] = (macro['spy_return'] - macro['spy_return'].rolling(252, min_periods=30).mean()) / (macro['spy_return'].rolling(252, min_periods=30).std() + 1e-9)
    macro['vix_z'] = (macro['vix_close'] - macro['vix_close'].rolling(252, min_periods=30).mean()) / (macro['vix_close'].rolling(252, min_periods=30).std() + 1e-9)
    
    macro.index = pd.to_datetime(macro.index).tz_localize(None)
    return macro[['spy_z', 'vix_z']]

# --- 3. PIPELINE & INFERENCE ---

def predict_trend(ticker_symbol, as_of: str = None):
    """Predict trend for `ticker_symbol`.

    If `as_of` (YYYY-MM-DD) is provided, historical data and macro context
    are fetched up to that date so the model behaves as if run on that day.
    """
    if model is None:
        raise RuntimeError("Model not initialized. Call init_predictor() first.")

    # 1. Fetch Data (anchor to as_of when provided)
    t = yf.Ticker(ticker_symbol)
    if as_of:
        df = t.history(period="2y", end=as_of)
    else:
        df = t.history(period="2y")

    if len(df) < 300:
        raise ValueError(f"Not enough historical data for {ticker_symbol} to calculate metrics.")

    df.columns = [c.lower() for c in df.columns]
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    # 2. Extract Features
    macro_df = get_macro_context(as_of=as_of)
    
    clean_df = df[['open', 'high', 'low', 'close']].copy()
    clean_df['ma_7'] = clean_df['close'].rolling(window=7).mean()
    clean_df['ma_21'] = clean_df['close'].rolling(window=21).mean()
    
    clean_df = clean_df.join(macro_df, how='left')
    clean_df['spy_z'] = clean_df['spy_z'].ffill().fillna(0)
    clean_df['vix_z'] = clean_df['vix_z'].ffill().fillna(0)

    raw_prices = clean_df[['open', 'high', 'low', 'close']].values.astype(float)
    safe_prices = raw_prices + 1e-10
    
    log_returns = np.log(safe_prices[1:, :4] / safe_prices[:-1, :4])
    log_returns = np.clip(log_returns, -0.5, 0.5)

    returns_df = pd.DataFrame(log_returns)
    rolling_mean = returns_df.rolling(window=252, min_periods=30).mean()
    rolling_std = returns_df.rolling(window=252, min_periods=30).std() + 1e-9
    rolling_z_scores = ((returns_df - rolling_mean) / rolling_std).values

    ma_7_dist = ((clean_df['close'] - clean_df['ma_7']) / clean_df['ma_7']).values[1:]
    ma_21_dist = ((clean_df['close'] - clean_df['ma_21']) / clean_df['ma_21']).values[1:]
    
    spy_z_aligned = clean_df['spy_z'].values[1:].reshape(-1, 1)
    vix_z_aligned = clean_df['vix_z'].values[1:].reshape(-1, 1)

    combined_features = np.hstack((
        rolling_z_scores, 
        np.nan_to_num(ma_7_dist).reshape(-1, 1),
        np.nan_to_num(ma_21_dist).reshape(-1, 1),
        spy_z_aligned,
        vix_z_aligned
    ))
    
    # 3. Slice the exact final 30 days needed for inference
    # (We drop NaN warmup rows implicitly by only grabbing the end of the array)
    recent_features = combined_features[-30:]
    input_tensor = torch.tensor(recent_features).float().unsqueeze(0).to(device)

    # 4. Predict
    with torch.no_grad():
        logits = model(input_tensor)
        
        # --- TEMPERATURE SCALING ---
        T = 1.65
        scaled_logits = logits / T
        
        # Convert to probabilities using the softened logits
        probs = F.softmax(scaled_logits, dim=1)[0]
    
    confidence, pred_class_tensor = torch.max(probs, dim=0)
    pred_class = pred_class_tensor.item()
    confidence_pct = confidence.item() * 100

    # Map the class index back to human-readable trends
    trend_map = {0: "Down", 1: "Neutral", 2: "Up"}
    predicted_trend = trend_map[pred_class]
    last_close = clean_df['close'].iloc[-1]

    # Print summary for teammates
    print("\n" + "=" * 40)
    print(f" AI METRIC FORECAST: {ticker_symbol.upper()}")
    print("=" * 40)
    print(f" Current Price : ${last_close:.2f}")
    print(f" 3-Day Outlook : {predicted_trend}")
    print(f" AI Certainty  : {confidence_pct:.2f}%")
    print("=" * 40)

    # Return a clean dictionary for the frontend developers to consume
    return {
        "ticker": ticker_symbol.upper(),
        "current_price": round(last_close, 2),
        "prediction_class": pred_class,
        "trend_label": predicted_trend,
        "confidence_pct": round(confidence_pct, 2)
    }

# --- TEST IT ---
if __name__ == "__main__":
    init_predictor()
    
    # Example usage for the app backend
    aapl_result = predict_trend("AAPL")
    msft_result = predict_trend("MSFT")
    predict_trend("NVDA")