export interface ApiError {
  message: string;
  status?: number;
}

export interface PredictionRequest {
  symbol?: string;
  ticker?: string;
  as_of?: string;
}

export interface TrendPredictionResponse {
  projected_direction: string;
  current_price: number;
  score: number;
  confidence: number;
  prediction_class?: number;
  trend_label?: string;
  confidence_pct?: number;
  reasoning?: string;
  timestamp?: string;
  fallback?: boolean;
  warning?: string;
}

export interface NewsPredictionResponse {
  score: number;
  confidence: number;
  reasoning: string;
}