import type { ApiError } from '../types/api';

const token = (): string => import.meta.env.VITE_DATABRICKS_TOKEN ?? '';

async function parseJsonResponse<TResponse>(response: Response): Promise<TResponse> {
  const raw = await response.text();

  try {
    return JSON.parse(raw) as TResponse;
  } catch {
    const preview = raw.slice(0, 120).replace(/\s+/g, ' ').trim();
    const err = new Error(
      `Expected JSON response but received non-JSON content. Preview: ${preview}`
    ) as Error & ApiError;
    err.status = response.status;
    throw err;
  }
}

export async function postJson<TResponse, TBody>(
  url: string,
  body: TBody
): Promise<TResponse> {
  // #LINKING This network call sends frontend payloads to backend model endpoints.
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token() ? { Authorization: `Bearer ${token()}` } : {})
    },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    let message = 'Unexpected API error.';
    try {
      const maybeError = await parseJsonResponse<{ message?: string }>(response);
      message = maybeError.message ?? message;
    } catch {
      message = response.statusText || message;
    }

    const err: ApiError = { message, status: response.status };
    throw err;
  }

  return parseJsonResponse<TResponse>(response);
}

export async function getJson<TResponse>(url: string): Promise<TResponse> {
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      ...(token() ? { Authorization: `Bearer ${token()}` } : {})
    }
  });

  if (!response.ok) {
    let message = 'Unexpected API error.';
    try {
      const maybeError = await parseJsonResponse<{ message?: string }>(response);
      message = maybeError.message ?? message;
    } catch {
      message = response.statusText || message;
    }

    const err: ApiError = { message, status: response.status };
    throw err;
  }

  return parseJsonResponse<TResponse>(response);
}
