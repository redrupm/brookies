import pandas as pd
import yfinance as yf
import concurrent.futures
from pathlib import Path
import sys
# Import your model logic here
# from models.trend import predict_trend 

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def _initialize_trend_model():
    """Initialize the trend prediction model from trend.py"""
    global _trend_model_initialized, _trend_model_error, _trend_module
    
    try:
        # Add trend directory to path so we can import trend.py directly
        trend_dir = str(BASE_DIR / "models")
        if trend_dir not in sys.path:
            sys.path.insert(0, trend_dir)
        
        # Import the trend module
        import trend
        _trend_module = trend
        
        # Initialize the model with the path to the saved model
        model_path = BASE_DIR / "models" / "trend_model.pth"
        if not model_path.exists():
            _trend_model_error = f"Model file not found: {model_path}"
            print(f"WARNING: {_trend_model_error}")
            return
        
        _trend_module.init_predictor(str(model_path))
        _trend_model_initialized = True
    except Exception as e:
        _trend_model_error = f"Failed to initialize trend model: {str(e)}"
        print(f"WARNING: {_trend_model_error}")

def get_trend_prediction(stock_ticker, as_of):
    # Get 3-day projections and current price from the loaded module
    result = _trend_module.predict_trend(stock_ticker, as_of=as_of)
    projected_direction = result.get('trend_label', None)
    confidence_pct = result.get('confidence_pct')
    current_price = result.get('current_price')

    # Calculate weighted score
    if (projected_direction == "Up"): # 6.66 to 10
        score = 6.66 + (confidence_pct / 100) * 3.34
        if confidence_pct >= 52.5:
            score = max(9, score)
        projected_direction = 1
    elif (projected_direction == "Neutral"): # 3.33 to 6.66
        score = 3.33 + (confidence_pct / 100) * 1.64
        projected_direction = 0
    else: # Down: 0 to 3.33
        score = 3.34 - (confidence_pct / 100) * 3.34
        projected_direction = -1
    
    return {
        "projected_direction": projected_direction,
        "current_price": round(current_price, 3),
        "score": round(score, 2),
        "confidence": round(confidence_pct, 2)
    }



def process_single_ticker(ticker):
    """
    Downloads history and generates model inferences for a single ticker.
    Runs on a separate CPU core.
    """

    if '_trend_module' not in globals():
        _initialize_trend_model()

    try:
        # 1. Load OHLCV Data
        df = yf.download(ticker, period="5y", progress=False)
        if df.empty:
            return None
            
        df = df.reset_index()
        df['Ticker'] = ticker
        
        # 2. Vectorized Feature Engineering
        # Normalize price (e.g., % change from a 200-day moving average)
        df['norm_price'] = df['Close'] / df['Close'].rolling(window=200).mean() - 1
        
        # 3. Apply your app.py models 
        # (In practice, vectorize this if your model supports batching, 
        # otherwise apply row-by-row)
        scores = []
        confidences = []
        directions = []
        
        for date in df['Date']:
            # TODO: MOCK INFERENCE: Replace with actual _trend_module.predict_trend()
            result = get_trend_prediction(ticker, as_of=date)
            scores.append(result['score'])
            confidences.append(result['confidence'])
            directions.append(result['projected_direction'])
            # scores.append(7.5) 
            # confidences.append(60.0)
            # directions.append(1) # 1 for Up, 0 for Neutral, -1 for Down
            
        df['score'] = scores
        df['confidence'] = confidences
        df['direction'] = directions
        
        # Drop NaNs from rolling averages
        return df.dropna()
        
    except Exception as e:
        print(f"Failed {ticker}: {e}")
        return None

def build_master_dataset(ticker_list, output_path="master_feed.parquet"):
    """
    Spins up worker processes to crunch the Russell 3000 simultaneously.
    """
    all_data = []
    
    # Unleash all available CPU cores
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = {executor.submit(process_single_ticker, t): t for t in ticker_list}
        
        for future in concurrent.futures.as_completed(futures):
            result_df = future.result()
            if result_df is not None:
                all_data.append(result_df)
                
    # Combine and save as a highly compressed Parquet file
    master_df = pd.concat(all_data, ignore_index=True)
    
    # Sort chronologically so our Gym environment can step through time easily
    master_df = master_df.sort_values(by=['Date', 'Ticker'])
    master_df.to_parquet(output_path, engine='pyarrow')
    print(f"Successfully compiled {len(master_df)} rows to {output_path}")


if __name__ == '__main__':
    _initialize_trend_model()
    
    data_path = BASE_DIR / 'models' / 'reinforcement-learning' / 'data'
    
    df_tickers = pd.read_csv(data_path / 'russel-3000-tickers.csv', header=None, names=['Ticker'])
    tickers = df_tickers['Ticker'].dropna().unique().tolist()

    build_master_dataset(tickers, data_path / 'master_feed.parquet')