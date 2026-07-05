import json
import pandas as pd
import yfinance as yf

def convert_tickers_excel_to_json(excel_file_path, output_json_path):
    try:
        # 1. Read the Excel file
        df = pd.read_excel(excel_file_path)
        
        # 2. Grab the first column automatically (assuming that's where your tickers are)
        # and clean up any accidental whitespace
        ticker_column = df.columns[0]
        tickers = df[ticker_column].dropna().astype(str).str.strip().unique()
        
        print(f"Found {len(tickers)} unique tickers. Fetching stock info from Yahoo Finance...")
        
        stocks_json_data = []
        
        # 3. Loop through each ticker and fetch details
        for i, ticker in enumerate(tickers, 1):
            # Clean ticker if it contains dots (e.g., BRK.B instead of BRK/B)
            formatted_ticker = ticker.replace('/', '-')
            
            try:
                stock = yf.Ticker(formatted_ticker)
                info = stock.info
                
                # Fetch details, fallback to "Unknown" if not found
                company_name = info.get('longName', 'Unknown Name')
                sector = info.get('sector', 'Unknown Sector')
                
                # If yfinance returned empty/mock data, label it appropriately
                if company_name == 'Unknown Name' and sector == 'Unknown Sector':
                    print(f"[{i}/{len(tickers)}] Warning: No data found for {ticker}")
                else:
                    print(f"[{i}/{len(tickers)}] Successfully fetched: {ticker}")
                
                # Append to our list in your exact required format
                stocks_json_data.append({
                    "ticker": ticker,
                    "company_name": company_name,
                    "sector": sector
                })
                
            except Exception as ticker_err:
                print(f"[{i}/{len(tickers)}] Error fetching {ticker}: {ticker_err}")
                stocks_json_data.append({
                    "ticker": ticker,
                    "company_name": "Unknown Name",
                    "sector": "Unknown Sector"
                })

        # 4. Save the finalized array to a JSON file
        with open(output_json_path, 'w', encoding='utf-8') as json_file:
            json.dump(stocks_json_data, json_file, indent=2, ensure_ascii=False)
            
        print(f"\nSuccess! Created '{output_json_path}' with {len(stocks_json_data)} entries.")
        
    except Exception as e:
        print(f"A critical error occurred: {e}")

# --- Run the Script ---
# Change 'tickers.xlsx' to whatever your excel sheet is named
convert_tickers_excel_to_json('../frontend/src/data/russel_3000.xlsx', '../frontend/src/data/3000_stocks.json')