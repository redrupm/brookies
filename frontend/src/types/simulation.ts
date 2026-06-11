export type SimulationChoice = 'buy' | 'sell' | 'keep';

export type SimulationStock = {
  ticker: string;
  price: number;
  amount: number;
  choice: SimulationChoice;
};

export type SimulationLog = {
  ticker: string;
  score: number;
  stockPrice: number;
  sharesHeld: number;
  cashBalance: number;
  stockValue: number;
  portfolioValue: number;
  portfolioChange: number;
  personalAmount: number;
  date: string;
  choice: SimulationChoice;
};

export type ParsedStocksPayload = {
  stocks: SimulationStock[];
};

export type PortfolioState = {
  cash: number;
  sharesByTicker: Record<string, number>;
  latestPrices: Record<string, number>;
};

export type SimulationProgress = {
  completed: number;
  total: number;
};