function resolveApiBaseUrl() {
  return 'http://localhost:8000';
}

// #LINKING Backend base URL used for all Databricks model-serving API calls.
export const API_BASE_URL = resolveApiBaseUrl();

export const TRENDS_ENDPOINT = `${API_BASE_URL}/api/trend-prediction`;

export const PRICES_ENDPOINT = `${API_BASE_URL}/api/prices`;