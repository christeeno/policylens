"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  type IChartApi,
  createChart,
} from "lightweight-charts";

const API_BASE = "http://localhost:8000";

const TIMEFRAMES = [
  { label: "1D", period: "1d", interval: "5m" },
  { label: "1W", period: "5d", interval: "30m" },
  { label: "1M", period: "1mo", interval: "1d" },
  { label: "6M", period: "6mo", interval: "1d" },
  { label: "1Y", period: "1y", interval: "1d" },
] as const;

type TimeframeLabel = (typeof TIMEFRAMES)[number]["label"];

interface StockChartProps {
  ticker: string;
}

interface HistoryRow {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number;
}

interface StockHistoryResponse {
  ticker: string;
  ohlcv: HistoryRow[];
}

export default function StockChart({ ticker }: StockChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [timeframe, setTimeframe] = useState<TimeframeLabel>("6M");
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const activeConfig = useMemo(
    () => TIMEFRAMES.find((item) => item.label === timeframe) ?? TIMEFRAMES[3],
    [timeframe],
  );

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          period: activeConfig.period,
          interval: activeConfig.interval,
        });
        const response = await fetch(
          `${API_BASE}/api/stocks/${encodeURIComponent(ticker)}/history?${params.toString()}`,
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const payload = (await response.json()) as StockHistoryResponse;
        if (!cancelled) {
          setHistory(Array.isArray(payload.ohlcv) ? payload.ohlcv : []);
        }
      } catch (fetchError) {
        console.error("Failed to fetch stock history:", fetchError);
        if (!cancelled) {
          setHistory([]);
          setError("Chart unavailable");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, [activeConfig.interval, activeConfig.period, ticker]);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 220,
      layout: {
        background: { type: ColorType.Solid, color: "#0f1724" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "rgba(148, 163, 184, 0.08)" },
        horzLines: { color: "rgba(148, 163, 184, 0.08)" },
      },
      crosshair: {
        vertLine: { color: "rgba(59, 130, 246, 0.35)" },
        horzLine: { color: "rgba(59, 130, 246, 0.35)" },
      },
      rightPriceScale: {
        borderColor: "rgba(148, 163, 184, 0.2)",
      },
      timeScale: {
        borderColor: "rgba(148, 163, 184, 0.2)",
        timeVisible: timeframe === "1D" || timeframe === "1W",
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#00d97e",
      downColor: "#ff4560",
      borderVisible: false,
      wickUpColor: "#00d97e",
      wickDownColor: "#ff4560",
      priceLineVisible: false,
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "",
      color: "#3b82f6",
    });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.72,
        bottom: 0,
      },
    });

    const rows = history.filter(
      (row) =>
        typeof row.open === "number" &&
        typeof row.high === "number" &&
        typeof row.low === "number" &&
        typeof row.close === "number",
    );

    candleSeries.setData(
      rows.map((row) => ({
        time: row.date,
        open: row.open as number,
        high: row.high as number,
        low: row.low as number,
        close: row.close as number,
      })),
    );

    volumeSeries.setData(
      rows.map((row) => ({
        time: row.date,
        value: row.volume,
        color: (row.close as number) >= (row.open as number) ? "rgba(0, 217, 126, 0.45)" : "rgba(255, 69, 96, 0.45)",
      })),
    );

    chart.timeScale().fitContent();
    chartRef.current = chart;

    return () => {
      chartRef.current = null;
      chart.remove();
    };
  }, [history, timeframe]);

  return (
    <div className="mt-3 rounded-lg border border-[#1e1e2e] bg-[#0f1724] p-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="text-[10px] uppercase tracking-[0.24em] text-[#6b7280]">
          Price Action
        </span>
        <div className="flex gap-1 rounded-md bg-[#111827] p-1">
          {TIMEFRAMES.map((option) => (
            <button
              key={option.label}
              type="button"
              onClick={() => setTimeframe(option.label)}
              className={`rounded px-2 py-1 text-[10px] font-semibold transition-colors ${
                timeframe === option.label
                  ? "bg-[#2563eb] text-white"
                  : "text-[#94a3b8] hover:bg-[#1f2937] hover:text-white"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex h-[220px] items-center justify-center text-xs text-[#6b6b8a]">
          Loading chart...
        </div>
      ) : error || history.length === 0 ? (
        <div className="flex h-[220px] items-center justify-center text-xs text-[#6b6b8a]">
          {error ?? `No price history found for ${ticker}.`}
        </div>
      ) : (
        <div ref={containerRef} className="h-[220px] w-full" aria-label={`${ticker} stock chart`} />
      )}
    </div>
  );
}
