"use client";

export const API_BASE = "http://localhost:8000";

export interface StockHistoryPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface StockHistoryResponse {
  ticker: string;
  interval: string;
  currency?: string | null;
  exchange_timezone?: string | null;
  ohlcv: StockHistoryPoint[];
}

export interface TechnicalScoreResponse {
  ticker: string;
  score: number;
  max_score?: number;
  label?: string;
  summary?: string;
  as_of?: string | null;
  breakdown?: Array<{
    key: string;
    label: string;
    value: string | number | null;
  }>;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed for ${path}`);
  }

  return response.json() as Promise<T>;
}

export function fetchStockHistory(ticker: string) {
  return fetchJson<StockHistoryResponse>(`/api/stocks/${encodeURIComponent(ticker)}/history?period=6mo&interval=1d`);
}

export function fetchTechnicalScore(ticker: string) {
  return fetchJson<TechnicalScoreResponse>(`/api/stocks/${encodeURIComponent(ticker)}/technical-score`);
}
