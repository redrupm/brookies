export interface StockData {
    stock: Stock;
    prices: StockPrices;
    metrics: Metrics;
    grade: string;
}

export interface StockCardData {
    stockData: StockData;
    grade: string;
    label: string;
}

export interface Stock {
    ticker: string;
    companyName: string;
    sector: string;
}   

export interface PricePoint {
    label: string;
    close: number;
}

export interface Metrics {
    trend: trendMetric;
    news: number;
    diversity: number;
    stability: number;
}

export interface trendMetric {
    projected_opens?: number[];
    current_price: number;
    score: number;
    confidence: number;
    prediction_class?: number;
    trend_label?: string;
    confidence_pct?: number;
    fallback?: boolean;
    warning?: string;
}

export interface StockPrices {
    '1D': PricePoint[];
    '5D': PricePoint[];
    '1M': PricePoint[];
    '6M': PricePoint[];
    '1Y': PricePoint[];
}