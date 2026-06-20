import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import StockPriceChart from '../components/StockPriceChart';
import { getStockData } from '../api/apiCaller';
import type { StockData, PricePoint } from '../types/stocks';

type TimelineOption = '1D' | '5D' | '1M' | '6M' | '1Y';
const TIMELINE_OPTIONS: TimelineOption[] = ['1D', '5D', '1M', '6M', '1Y'];

function getChangePercent(points: PricePoint[] | undefined): number {
  if (!points || points.length < 2) return 0;
  const first = points[0].close;
  const last = points[points.length - 1].close;
  return ((last - first) / first) * 100;
}

function buildPortfolioInsight() {
  // Minimal placeholder: real logic can be plugged in later
  return {
    diversityScore: 5,
    diversityRationale: 'Moderate sector spread',
    stabilityScore: 5,
    stabilityRationale: 'Stable historical volatility'
  };
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export default function StockDetail() {
  const { symbol } = useParams();
  const navigate = useNavigate();
  const normalizedSymbol = (symbol ?? '').toUpperCase();

  const [loading, setLoading] = useState(true);
  const [stockData, setStockData] = useState<StockData | null>(null);
  const [selectedTimeline, setSelectedTimeline] = useState<TimelineOption>('1M');
  const [holdings, setHoldings] = useState<Array<{ symbol: string; shares: number }>>([]);

  useEffect(() => {
    // load simple holdings from localStorage (if used elsewhere)
    try {
      const raw = localStorage.getItem('holdings');
      if (raw) {
        setHoldings(JSON.parse(raw));
      } else {
        
      }  
    } catch {
      setHoldings([]);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!normalizedSymbol) return;
      setLoading(true);
      try {
        const data = await getStockData(normalizedSymbol);
        if (cancelled) return;
        setStockData(data);
      } catch (err) {
        console.error('Failed to load stock data', err);
        setStockData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [normalizedSymbol]);

  function removeHolding(symbolToRemove: string) {
    const next = holdings.filter((h) => h.symbol !== symbolToRemove);
    setHoldings(next);
    try {
      localStorage.setItem('holdings', JSON.stringify(next));
    } catch {}
  }

  if (loading) {
    return (
      <section className="page">
        <div className="panel">
          <h2>Loading Stock Data</h2>
          <p className="placeholder">Refreshing latest market history...</p>
        </div>
      </section>
    );
  }

  if (!stockData) {
    return (
      <section className="page">
        <div className="panel">
          <h2>Stock Not Found</h2>
          <p className="placeholder">This ticker was not found. Try returning to the dashboard.</p>
          <button onClick={() => navigate('/')}>Go to Dashboard</button>
        </div>
      </section>
    );
  }

  const stock = stockData.stock;
  const visiblePrices = (stockData.prices as any)[selectedTimeline] ?? [];
  const changePercent = getChangePercent(visiblePrices as PricePoint[]);
  const latestPrice = visiblePrices[visiblePrices.length - 1]?.close ?? 0;
  const holding = holdings.find((h) => h.symbol === stock.ticker);
  const insight = buildPortfolioInsight();
  const trendScore = stockData.metrics.trend?.score ?? 0;
  let trendRationale: string;
  if (stockData.metrics.trend?.fallback) {
    trendRationale = `Trend model unavailable; neutral score used${stockData.metrics.trend.warning ? ` (${stockData.metrics.trend.warning})` : ''}`;
  } else {
    const projectedDirection = stockData.metrics.trend.projected_direction;
    const confidence = stockData.metrics.trend.confidence;
    if (!projectedDirection || !confidence) {
      trendRationale = 'Trend model returned incomplete price data.';
    } else {
      trendRationale = `Trend predicted to go ${projectedDirection} over the next 3 days with a confidence of ${confidence}`;
    }
  }

  const displayMetrics = [
    { name: 'News', score: stockData.metrics.news.score ?? 0, rationale: stockData.metrics.news.rationale },
    { name: 'Trend', score: trendScore, rationale: trendRationale },
    { name: 'Diversity', score: insight.diversityScore, rationale: insight.diversityRationale },
    { name: 'Stability', score: insight.stabilityScore, rationale: insight.stabilityRationale }
  ];

  return (
    <section className="page">
      <div className="panel detail-header">
        <div>
          <p className="eyebrow">Stock Detail</p>
          <h1>
            {stock.ticker} • {stock.companyName}
          </h1>
          <p className="stock-state-line">
            ${latestPrice.toFixed(2)} • {selectedTimeline} change •{' '}
            <span className={changePercent >= 0 ? 'up' : 'down'}>
              {changePercent >= 0 ? '+' : ''}
              {changePercent.toFixed(2)}%
            </span>
          </p>
        </div>

        <div className="detail-actions">
          {holding ? (
            <button onClick={() => removeHolding(holding.symbol)}>Remove From My Holdings</button>
          ) : null}
        </div>
      </div>

      <div className="panel">
        <div className="timeline-header">
          <h2>Price Timeline</h2>
          <div className="timeline-selector" role="tablist" aria-label="Price timeline range">
            {TIMELINE_OPTIONS.map((option) => (
              <button key={option} type="button" className={option === selectedTimeline ? 'active' : ''} onClick={() => setSelectedTimeline(option)}>
                {option}
              </button>
            ))}
          </div>
        </div>
        <StockPriceChart data={visiblePrices as PricePoint[]} />
      </div>

      <div className="detail-grid">
        <div className="panel metric-breakdown">
          <h3>Metric Breakdown</h3>
          <p className="placeholder">These scores explain why this stock currently has a grade.</p>

          <div className="metric-breakdown-list">
            {displayMetrics.map((metric) => (
              <article key={metric.name} className="metric-explainer">
                <div className="metric-explainer-head">
                  <p>{metric.name}</p>
                  <strong>{metric.score.toFixed(1)}/10</strong>
                </div>
                <p>{metric.rationale}</p>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
