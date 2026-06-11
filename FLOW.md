# Dashboard

## Get all stock data

Dashboard.tsx: load()
                L> apiCaller.getAllStockData()
                L> setStockData()
                
apiCaller.tsx: getAllStockData()
                    L> getStockData(string: Ticker) 
                            L> prices
                            L> trendPrediction
                            L> newsPrediction
                            L> calculateDiversity
                            L> caluclateVelocity
                            L> calculateGrade

### Prices

app.py: get_stock_prices()


# Types

StockPrices {
    '1D': PricePoint[]
    '5D': PricePoint[]
    '1M': PricePoint[]
    '6M': PricePoint[]
    '1Y': PricePoint[]
}
