import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import threading
import yfinance as yf
import numpy as np
import json

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_BUILD_DIR = BASE_DIR / "frontend" / "build"

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

_trend_model_initialized = False
_trend_model_error = None
_trend_module = None

@app.post("/api/prices")
def get_stock_prices():
    """API endpoint to get stock price data for target stock"""
    # Get stock ticker from request body
    data = request.get_json()
    stock = data.get("ticker")

    try:
        ret_prices = {}
        # All display time periods and intervals
        ret_labels = {'1d': ('1D', '15m'), 
                      '5d': ('5D', '1h'), 
                      '1mo': ('1M', '1d'), 
                      '6mo': ('6M', '1wk'), 
                      '1y': ('1Y', '1wk')}
        for label, (key, interval) in ret_labels.items():
            ticker = yf.Ticker(stock)
            stock_history = ticker.history(period=label, interval=interval)
            prices = [
                {
                    "label": str(date.date()),
                    "close": round(p, 3)
                }
                for date, p in zip(stock_history.index, stock_history['Close'])
            ]
            ret_prices[key] = prices
        return jsonify(ret_prices)
    except Exception as e:
        print(f"Error fetching stock prices: {e}", file=sys.stderr)
        return jsonify({"error": "Failed to fetch stock price"}), 500

@app.post("/api/trend-prediction")
def get_trend_prediction():
    """API endpoint to get stock trend prediction data for target stock"""
    data = request.get_json()
    stock_ticker = data.get("ticker")
    as_of = data.get("as_of")

    if not stock_ticker:
        return jsonify({"error": "Missing ticker or symbol in request body"}), 400

    if not _trend_model_initialized:
        # Fall back to a neutral prediction instead of crashing the request path.
        # This keeps portfolio/data screens usable when ML deps are unavailable.
        try:
            ticker = yf.Ticker(stock_ticker)
            history = ticker.history(period="5d", interval="1d")
            closes = [
                round(p, 3)
                for p in history.get("Close", [])
            ]
            current_price = closes[-1] if closes else 0.0
        except Exception:
            current_price = 0.0

        projected_opens = [current_price, current_price, current_price]

        projectedAverage = sum(projected_opens) / len(projected_opens)
        percentChange = ((projectedAverage - current_price) / current_price) * 100 if current_price else 0
        if percentChange > 0:
            score = percentChange * 175
            if score > 10:
                score = 10
        else:
            score = 0
        

        return jsonify({
            "projected_opens": projected_opens,
            "current_price": current_price,
            "score": score,
            "confidence": 0.0,
            "fallback": True,
            "warning": _trend_model_error or "Trend model not initialized",
        })

     # Get 3-day projections and current price from the loaded module
    result = _trend_module.predict_trend(stock_ticker, as_of=as_of)
    projected_direction = result.get('trend_label', None)
    confidence_pct = result.get('confidence_pct')
    current_price = result.get('current_price')

    # Calculate score
    if (projected_direction == "Up"): # 6.66 to 10
        score = 6.66 + (confidence_pct / 100) * 3.34
        if confidence_pct >= 52.5:
            score = max(9, score)
    elif (projected_direction == "Neutral"): # 3.33 to 6.66
        score = 3.33 + (confidence_pct / 100) * 1.64
    else: # Down: 0 to 3.33
        score = 3.34 - (confidence_pct / 100) * 3.34
    
    print(f"Trend prediction for {stock_ticker}: projected_direction={projected_direction}, current_price={current_price}, score={score:.2f}, confidence={confidence_pct:.2f}")
    return jsonify({
        "projected_direction": projected_direction,
        "current_price": round(current_price, 3),
        "score": round(score, 2),
        "confidence": round(confidence_pct, 2)
    })

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
        print("Trend model initialized successfully")
    except Exception as e:
        _trend_model_error = f"Failed to initialize trend model: {str(e)}"
        print(f"WARNING: {_trend_model_error}")


if __name__ == "__main__":
    # Initialize models on startup
    _initialize_trend_model()
    # _initialize_news_model()
    # if os.getenv("PRECOMPUTE_TRENDS", "0").lower() in {"1", "true", "yes"}:
    #     _compute_trend_predictions()
    
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))