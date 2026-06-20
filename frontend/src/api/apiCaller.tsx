import type { StockData, StockPrices } from '../types/stocks';
import stocks from '../data/test_stocks.json'; //TODO
import { postJson } from './client';
import { PRICES_ENDPOINT, TRENDS_ENDPOINT, NEWS_ENDPOINT } from './endpoints';
import type { PredictionRequest, TrendPredictionResponse, NewsPredictionResponse } from '../types/api';

function delay(ms: number) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

export async function getAllStockData(): Promise<StockData[]> {
    const CACHE_KEY = 'stock_prices_cache_v1';

    // // Try localStorage cache first
    // try {
    //     const raw = localStorage.getItem(CACHE_KEY);
    //     if (raw) {
    //         const parsed = JSON.parse(raw) as { lastCache: number; stocks: StockData[] };
    //         if (parsed?.lastCache && (Date.now() - parsed.lastCache) < CACHE_TTL) {
    //             return parsed.stocks;
    //         }
    //     }
    // } catch (err) {
    //     console.warn('Failed to read cache from localStorage:', err);
    // }

    const results: StockData[] = [];
    for (const s of stocks) {
        await delay(500);
        console.log(`Fetching data for ${s.ticker}...`);
        const data = await getStockData(s.ticker);
        console.log(`Received data for ${s.ticker}:`, data);
        results.push(data);
    }

    // Save to cache
    try {
        const payload = { lastCache: Date.now(), stocks: results };
        localStorage.setItem(CACHE_KEY, JSON.stringify(payload));
    } catch (err) {
        console.warn('Failed to save cache to localStorage:', err);
    }

    return results;
}

export async function getStockData(ticker: string): Promise<StockData> {
        try {
            // Stock info
            const stock = {
                'ticker': ticker,
                'companyName': stocks.find(s => s.ticker === ticker)?.company_name ?? '',
                'sector': stocks.find(s => s.ticker === ticker)?.sector ?? ''
            }

            // Get stock prices data
            const prices = await postJson<StockPrices, { ticker: string }>(PRICES_ENDPOINT,
                { ticker }
            );

            // Get trend prediction data
            const trendPrediction = await postJson<TrendPredictionResponse, PredictionRequest>(
                TRENDS_ENDPOINT,
                { ticker: stock.ticker }
            );

            // Get news prediction data
            const newsPrediction = await postJson<NewsPredictionResponse, PredictionRequest>(
                NEWS_ENDPOINT,
                { ticker: stock.ticker }
            );
            
            // Calculate grade using metrics
            let grade = null;
            const metricAverage  = (trendPrediction.score + newsPrediction.score) / 2;
            if (metricAverage >= 6.66) {
                grade = 'A';
            } else if (metricAverage >= 3.33) {
                grade = 'B';
            } else {
                grade = 'C';
            }
            return {stock, prices, metrics: { trend: trendPrediction, news: newsPrediction, diversity: 0, stability: 0 }, grade};
        } catch(err) {
            console.error(`Failed to get trend prediction for ${ticker}:`, err);
        }
        return null as unknown as StockData;
}
