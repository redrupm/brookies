import { useEffect, useState, type ChangeEvent } from 'react';
import { postJson } from '../api/client';
import { TRENDS_ENDPOINT } from '../api/endpoints';
import type { PredictionRequest, TrendPredictionResponse } from '../types/api';
import topStocks from '../data/top_stocks.json';
import type {
  SimulationChoice,
  SimulationLog,
  SimulationProgress,
  SimulationStock,
  ParsedStocksPayload,
  PortfolioState,
} from '../types/simulation';

// ─── Constants ────────────────────────────────────────────────────────────────

const SIMULATION_STEP_DAYS = 3;

const DEFAULT_JSON = JSON.stringify(
  {
    stocks: topStocks.map((stock) => ({
      ticker: stock.ticker,
      company_name: stock.company_name,
      sector: stock.sector,
      amount: 0,
      choice: 'keep',
    })),
  },
  null,
  2
);

// ─── Formatting ───────────────────────────────────────────────────────────────

function formatMoney(value: number) {
  return `$${value.toFixed(2)}`;
}

function formatDate(value: string) {
  if (!value) return '—';
  const parsed = parseDateInput(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString();
}

// ─── Date helpers ─────────────────────────────────────────────────────────────

function parseDateInput(value: string) {
  return new Date(`${value}T12:00:00`);
}

function toDateKey(date: Date) {
  return date.toISOString().slice(0, 10);
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function buildDateSeries(startDate: string, endDate: string) {
  const start = parseDateInput(startDate);
  const end = parseDateInput(endDate);
  const dates: string[] = [];

  for (
    let current = new Date(start);
    current <= end;
    current = addDays(current, SIMULATION_STEP_DAYS)
  ) {
    dates.push(toDateKey(current));
  }

  return dates;
}

function clampRisk(value: number) {
  return Math.min(100, Math.max(0, value));
}

// ─── Thresholds ───────────────────────────────────────────────────────────────

function getBuyThreshold(risk: number) {
  if (risk < 34) return 9;
  if (risk < 67) return 7.5;
  return 6;
}

function getSellThreshold() {
  return 4.5;
}

function getAction(score: number, risk: number): SimulationChoice {
  if (score <= getSellThreshold()) return 'sell';
  if (score >= getBuyThreshold(risk)) return 'buy';
  return 'keep';
}

// ─── Parsing ──────────────────────────────────────────────────────────────────

function parseStocksPayload(input: string): ParsedStocksPayload {
  const raw = JSON.parse(input) as unknown;

  if (Array.isArray(raw)) {
    return { stocks: raw.map(normalizeStock) };
  }

  if (
    raw &&
    typeof raw === 'object' &&
    'stocks' in raw &&
    Array.isArray((raw as { stocks: unknown[] }).stocks)
  ) {
    return { stocks: (raw as { stocks: unknown[] }).stocks.map(normalizeStock) };
  }

  throw new Error('Expected a stocks array or an object with a stocks array.');
}

function normalizeStock(value: unknown): SimulationStock {
  if (!value || typeof value !== 'object') {
    throw new Error('Each stock entry must be an object.');
  }

  const stock = value as Record<string, unknown>;
  const ticker = String(stock.ticker ?? stock.symbol ?? '').trim().toUpperCase();
  const price = Number(stock.price ?? stock.currentPrice ?? stock.close ?? 0);
  const amount = Number(stock.amount ?? stock.quantity ?? stock.shares ?? 0);
  const rawChoice = String(stock.choice ?? stock.action ?? 'keep').toLowerCase();
  const choice: SimulationChoice =
    rawChoice === 'buy' || rawChoice === 'sell' ? rawChoice : 'keep';

  if (!ticker) throw new Error('Each stock entry needs a ticker.');

  return {
    ticker,
    price: Number.isFinite(price) ? price : 0,
    amount: Number.isFinite(amount) ? amount : 0,
    choice,
  };
}

// ─── Portfolio math ───────────────────────────────────────────────────────────

function getPortfolioValue(state: PortfolioState) {
  return (Object.entries(state.sharesByTicker) as Array<[string, number]>).reduce(
    (sum, [ticker, shares]) => sum + shares * (state.latestPrices[ticker] ?? 0),
    0
  );
}

// ─── Simulation runner ────────────────────────────────────────────────────────

async function buildLogs(
  stocks: SimulationStock[],
  startDate: string,
  endDate: string,
  risk: number,
  startingAmount: number,
  onProgress?: (progress: SimulationProgress) => void
): Promise<SimulationLog[]> {
  const dates = buildDateSeries(startDate, endDate);

  const state: PortfolioState = {
    cash: startingAmount,
    sharesByTicker: Object.fromEntries(stocks.map((s) => [s.ticker, 0])),
    latestPrices: Object.fromEntries(stocks.map((s) => [s.ticker, s.price])),
  };

  const logs: SimulationLog[] = [];
  const totalSteps = dates.length * stocks.length;
  let completedSteps = 0;

  for (const date of dates) {
    // Fetch predictions for all stocks on this date
    const predictions: TrendPredictionResponse[] = [];

    for (const stock of stocks) {
      const prediction = await postJson<TrendPredictionResponse, PredictionRequest>(
        TRENDS_ENDPOINT,
        { ticker: stock.ticker, as_of: date }
      );
      predictions.push(prediction);
      completedSteps += 1;
      onProgress?.({ completed: completedSteps, total: totalSteps });
    }

    // Score each stock and decide action
    const scoredStocks = stocks.map((stock, index) => {
      const prediction = predictions[index];
      const score = Number(prediction.score ?? 0);
      const stockPrice = Number(prediction.current_price ?? stock.price ?? 0);
      state.latestPrices[stock.ticker] = stockPrice;
      return { stock, score, stockPrice, choice: getAction(score, risk) };
    });

    const sellCandidates = scoredStocks.filter(({ choice }) => choice === 'sell');
    const strongBuys = scoredStocks.filter(
      ({ choice, score }) => choice === 'buy' && score >= getBuyThreshold(risk)
    );
    // Fall back to the highest-scored stock if nothing qualifies as a strong buy
    const activeBuys = strongBuys.length
      ? strongBuys
      : scoredStocks.slice().sort((a, b) => b.score - a.score).slice(0, 1);

    // Sell phase: liquidate all shares of sell candidates
    for (const { stock, stockPrice } of sellCandidates) {
      const heldShares = state.sharesByTicker[stock.ticker] ?? 0;
      if (heldShares <= 0) continue;
      state.cash += heldShares * stockPrice;
      state.sharesByTicker[stock.ticker] = 0;
    }

    // Buy phase: distribute cash proportionally by score
    const totalWeight = activeBuys.reduce(
      (sum, { score }) => sum + Math.max(score, 0.01),
      0
    );
    const buyPool = state.cash;

    for (const [i, candidate] of activeBuys.entries()) {
      const { stock, score, stockPrice } = candidate;
      const weight = totalWeight > 0 ? score / totalWeight : 1 / activeBuys.length;
      // Give any rounding remainder to the last candidate
      const allocation = i === activeBuys.length - 1 ? state.cash : buyPool * weight;
      const sharesToBuy = stockPrice > 0 ? allocation / stockPrice : 0;

      if (sharesToBuy > 0) {
        state.cash -= sharesToBuy * stockPrice;
        state.sharesByTicker[stock.ticker] =
          (state.sharesByTicker[stock.ticker] ?? 0) + sharesToBuy;
      }
    }

    // Sweep any leftover cash into the top buy candidate
    if (state.cash > 0.01 && activeBuys.length > 0) {
      const fallback = activeBuys[0];
      const fallbackPrice = Math.max(fallback.stockPrice, 0.01);
      state.sharesByTicker[fallback.stock.ticker] =
        (state.sharesByTicker[fallback.stock.ticker] ?? 0) + state.cash / fallbackPrice;
      state.cash = 0;
    }

    // Record a log entry for every stock at this date
    for (const { stock, score, stockPrice, choice } of scoredStocks) {
      const sharesHeld = state.sharesByTicker[stock.ticker] ?? 0;
      const stockValue = sharesHeld * stockPrice;
      const portfolioValue = Number(getPortfolioValue(state).toFixed(2));

      logs.push({
        ticker: stock.ticker,
        score,
        stockPrice,
        sharesHeld,
        cashBalance: Number(state.cash.toFixed(2)),
        stockValue: Number(stockValue.toFixed(2)),
        portfolioValue,
        portfolioChange: Number((portfolioValue - startingAmount).toFixed(2)),
        personalAmount: portfolioValue,
        date,
        choice,
      });
    }

    state.cash = Number(state.cash.toFixed(6));

    // Final sweep — safety net in case rounding left a residual
    if (state.cash > 0.01) {
      const fallback = activeBuys[0];
      state.sharesByTicker[fallback.stock.ticker] =
        (state.sharesByTicker[fallback.stock.ticker] ?? 0) +
        state.cash / Math.max(fallback.stockPrice, 0.01);
      state.cash = 0;
    }
  }

  return logs;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function Simulation() {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [risk, setRisk] = useState(45);
  const [startingAmount, setStartingAmount] = useState(1000);
  const [jsonText, setJsonText] = useState(DEFAULT_JSON);
  const [selectedFileName, setSelectedFileName] = useState('');
  const [parseError, setParseError] = useState('');
  const [parsedStocks, setParsedStocks] = useState<SimulationStock[]>([]);
  const [logs, setLogs] = useState<SimulationLog[]>([]);
  const [lastRunSummary, setLastRunSummary] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [simulationError, setSimulationError] = useState('');
  const [simulationProgress, setSimulationProgress] = useState<SimulationProgress>({
    completed: 0,
    total: 0,
  });

  // Re-parse stocks whenever the JSON text changes
  useEffect(() => {
    try {
      const payload = parseStocksPayload(jsonText);
      setParsedStocks(payload.stocks);
      setParseError('');
    } catch (error) {
      setParsedStocks([]);
      setParseError(error instanceof Error ? error.message : 'Invalid JSON input.');
    }
  }, [jsonText]);

  // ─── Derived state ───────────────────────────────────────────────────────────

  const canRun = Boolean(
    startDate && endDate && parsedStocks.length && !parseError && !isRunning
  );
  const riskLabel = risk < 34 ? 'Low' : risk < 67 ? 'Moderate' : 'High';
  const buyThreshold = getBuyThreshold(risk);
  const sellThreshold = getSellThreshold();

  // ─── Handlers ────────────────────────────────────────────────────────────────

  async function handleRunSimulation() {
    if (!canRun) return;

    setIsRunning(true);
    setSimulationError('');
    setSimulationProgress({
      completed: 0,
      total: parsedStocks.length * buildDateSeries(startDate, endDate).length,
    });

    try {
      const nextLogs = await buildLogs(
        parsedStocks,
        startDate,
        endDate,
        risk,
        startingAmount,
        setSimulationProgress
      );

      setLogs(nextLogs);

      const finalPortfolio = nextLogs.length
        ? nextLogs[nextLogs.length - 1].portfolioValue
        : startingAmount;
      const netChange = finalPortfolio - startingAmount;
      const direction = netChange >= 0 ? 'up' : 'down';
      const stepCount = Math.max(1, Math.ceil(nextLogs.length / parsedStocks.length));

      setLastRunSummary(
        `${nextLogs.length} log entries generated across ${stepCount} simulation steps. ` +
          `Portfolio ended ${direction} ${formatMoney(Math.abs(netChange))} at ${formatMoney(finalPortfolio)}.`
      );
    } catch (error) {
      setSimulationError(error instanceof Error ? error.message : 'Simulation failed.');
      setLastRunSummary('');
      setLogs([]);
    } finally {
      setIsRunning(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setSelectedFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => setJsonText(String(reader.result ?? ''));
    reader.readAsText(file);
  }

  function handleJsonTextChange(value: string) {
    setJsonText(value);
    setSelectedFileName('');
  }

  function handleReset() {
    setStartDate('');
    setEndDate('');
    setRisk(45);
    setStartingAmount(1000);
    setJsonText(DEFAULT_JSON);
    setSelectedFileName('');
    setParseError('');
    setSimulationError('');
    setLogs([]);
    setLastRunSummary('');
    setSimulationProgress({ completed: 0, total: 0 });
  }

  // ─── Render ──────────────────────────────────────────────────────────────────

  return (
    <section className="page simulation-shell">

      {/* ── Hero ── */}
      <div className="panel hero-panel">
        <p className="eyebrow">Simulation</p>
        <h1>Scenario workspace for testing buy, sell, and keep decisions.</h1>
        <p>
          Choose a date range, paste or upload your stocks.json-style input, and run a
          read-only simulation log every 3 days using historical trend scores.
        </p>
      </div>

      <div className="simulation-grid">

        {/* ── Left column ── */}
        <div className="simulation-stack">

          {/* Date window */}
          <div className="panel">
            <div className="field-group">
              <div className="helper-row">
                <div>
                  <h2>Simulation Window</h2>
                  <p className="placeholder">Pick the start and end dates for the run.</p>
                </div>
              </div>
              <div className="field-row">
                <label>
                  Start Date
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                  />
                </label>
                <label>
                  End Date
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                  />
                </label>
              </div>
              <label>
                Starting Dollar Amount
                <input
                  type="number"
                  min={0}
                  step="10"
                  value={startingAmount}
                  onChange={(e) => setStartingAmount(Math.max(0, Number(e.target.value) || 0))}
                />
              </label>
            </div>
          </div>

          {/* Stocks JSON input */}
          <div className="panel">
            <div className="field-group">
              <div className="helper-row">
                <div>
                  <h2>Stocks Input</h2>
                  <p className="placeholder">
                    Paste JSON or upload a file that looks like a stocks.json payload.
                  </p>
                </div>
                <label className="subtle-link" style={{ cursor: 'pointer' }}>
                  Upload JSON
                  <input
                    type="file"
                    accept="application/json,.json"
                    onChange={handleFileChange}
                    style={{ display: 'none' }}
                  />
                </label>
              </div>

              <textarea
                className="json-editor"
                value={jsonText}
                onChange={(e) => handleJsonTextChange(e.target.value)}
                spellCheck={false}
                aria-label="Stocks JSON input"
              />

              <div className="helper-row">
                <p className="placeholder">
                  {selectedFileName
                    ? `Loaded file: ${selectedFileName}`
                    : 'Use the default sample or replace it with your own list.'}
                </p>
                {parseError
                  ? <p className="simulation-error">{parseError}</p>
                  : <p className="simulation-success">{parsedStocks.length} stocks ready.</p>}
              </div>
            </div>
          </div>
        </div>

        {/* ── Right column ── */}
        <div className="simulation-stack">

          {/* Risk meter */}
          <div className="panel">
            <div className="risk-meter">
              <div className="helper-row">
                <div>
                  <h2>Risk Meter</h2>
                  <p className="placeholder">
                    Low risk buys only score 9+; high risk buys score 6+; sell at 4.5 or below.
                  </p>
                </div>
                <span className="risk-pill">{riskLabel} risk</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={risk}
                onChange={(e) => setRisk(clampRisk(Number(e.target.value)))}
                aria-label="Simulation risk level"
              />
            </div>
          </div>

          {/* Controls + progress + summary cards */}
          <div className="panel">
            <div className="simulation-actions">
              <button onClick={handleRunSimulation} disabled={!canRun}>
                Run Simulation
              </button>
              <button onClick={handleReset} type="button">Reset</button>
            </div>

            {/* Progress bar */}
            <div className="simulation-progress" aria-label="Simulation loading progress">
              <div className="simulation-progress-track">
                <div
                  className="simulation-progress-fill"
                  style={{
                    width: simulationProgress.total
                      ? `${(simulationProgress.completed / simulationProgress.total) * 100}%`
                      : '0%',
                  }}
                />
              </div>
              <div className="helper-row">
                <p className="placeholder">
                  {simulationProgress.total
                    ? `${simulationProgress.completed} of ${simulationProgress.total} trend checks complete`
                    : 'No simulation progress yet.'}
                </p>
                <p className="placeholder">
                  {simulationProgress.total
                    ? `${Math.round((simulationProgress.completed / simulationProgress.total) * 100)}%`
                    : '0%'}
                </p>
              </div>
            </div>

            <p className="placeholder">
              {isRunning
                ? 'Running historical simulation...'
                : lastRunSummary || 'Run the scenario to generate a read-only log table below.'}
            </p>
            {simulationError && <p className="simulation-error">{simulationError}</p>}

            {/* Summary cards */}
            <div className="simulation-summary">
              <div className="summary-card">
                <p>Stocks</p>
                <strong>{parsedStocks.length}</strong>
              </div>
              <div className="summary-card">
                <p>Date Range</p>
                <strong>
                  {startDate && endDate
                    ? `${formatDate(startDate)} - ${formatDate(endDate)}`
                    : 'Not set'}
                </strong>
              </div>
              <div className="summary-card">
                <p>Risk</p>
                <strong>{risk}%</strong>
              </div>
              <div className="summary-card">
                <p>Buy Threshold</p>
                <strong>{buyThreshold.toFixed(1)}+</strong>
              </div>
              <div className="summary-card">
                <p>Sell Threshold</p>
                <strong>{sellThreshold.toFixed(1)} or less</strong>
              </div>
              <div className="summary-card">
                <p>Starting Amount</p>
                <strong>{formatMoney(startingAmount)}</strong>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Log table ── */}
      <div className="panel">
        <div className="helper-row">
          <div>
            <h2>Simulation Logs</h2>
            <p className="placeholder">Read-only output after each 3-day run.</p>
          </div>
          <p className="placeholder">{logs.length ? `${logs.length} rows` : 'No results yet'}</p>
        </div>

        <div className="simulation-table-wrap">
          <table className="simulation-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Score</th>
                <th>Shares Held</th>
                <th>Stock Price</th>
                <th>Stock Value</th>
                <th>Cash</th>
                <th>Portfolio Value</th>
                <th>Change</th>
                <th>Date</th>
                <th>Choice</th>
              </tr>
            </thead>
            <tbody>
              {logs.length ? (
                logs.map((row) => (
                  <tr key={`${row.ticker}-${row.date}-${row.choice}`}>
                    <td>{row.ticker}</td>
                    <td>{row.score.toFixed(2)}</td>
                    <td>{row.sharesHeld}</td>
                    <td>{formatMoney(row.stockPrice)}</td>
                    <td>{formatMoney(row.stockValue)}</td>
                    <td>{formatMoney(row.cashBalance)}</td>
                    <td>{formatMoney(row.portfolioValue)}</td>
                    <td>{formatMoney(row.portfolioChange)}</td>
                    <td>{formatDate(row.date)}</td>
                    <td className={`action-${row.choice}`}>{row.choice}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={10} className="placeholder">
                    No simulation logs generated yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}