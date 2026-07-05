export interface StockData {
    stock: Stock;
    prices: StockPrices;
    metrics: Metrics;
    grade: string;
}

export interface StockCardData {
    stockData: StockData;
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
    news: newsMetric;
    diversity: number;
    stability: number;
}

export interface trendMetric {
    projected_opens?: number[];
    projected_direction: string;
    current_price: number;
    score: number;
    confidence: number;
    prediction_class?: number;
    trend_label?: string;
    confidence_pct?: number;
    fallback?: boolean;
    warning?: string;
}

export interface newsMetric {
    score: number;
    confidence: number;
    rationale: string;
}

export interface StockPrices {
    '1D': PricePoint[];
    '5D': PricePoint[];
    '1M': PricePoint[];
    '6M': PricePoint[];
    '1Y': PricePoint[];
}