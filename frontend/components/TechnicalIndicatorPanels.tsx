"use client";

import React from "react";

const INDICATOR_ORDER = ["RSI", "MACD", "EMA20", "EMA50", "EMA200", "ADX", "ATR"] as const;

type IndicatorKey = (typeof INDICATOR_ORDER)[number];

type IndicatorValue = number | string | null | undefined;

export interface TechnicalIndicatorsPayload {
  ticker: string;
  as_of?: string | null;
  indicators?: Partial<Record<IndicatorKey, IndicatorValue>> | null;
}

interface IndicatorCardProps {
  label: IndicatorKey;
  value: IndicatorValue;
}

function formatIndicatorValue(value: IndicatorValue) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  }

  return String(value);
}

function IndicatorCard({ label, value }: IndicatorCardProps) {
  return (
    <div className="rounded-xl border border-[#1e1e2e] bg-[#12121a] p-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#6b6b8a]">
        {label}
      </div>
      <div className="mt-3 text-2xl font-semibold text-[#e8e8f0]">
        {formatIndicatorValue(value)}
      </div>
    </div>
  );
}

export default function TechnicalIndicatorPanels({
  ticker,
  indicators,
  loading,
  error,
  asOf,
}: {
  ticker: string;
  indicators: Partial<Record<IndicatorKey, IndicatorValue>> | null;
  loading: boolean;
  error: string | null;
  asOf?: string | null;
}) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-[#e8e8f0]">
            Technical Indicators
          </h3>
          <p className="mt-1 text-xs text-[#6b6b8a]">
            {ticker ? `Backend values for ${ticker}` : "Select a stock to view indicators"}
          </p>
        </div>
        {asOf ? (
          <span className="text-[11px] font-mono text-[#6b6b8a]">
            As of {asOf}
          </span>
        ) : null}
      </div>

      {loading ? (
        <div className="rounded-xl border border-[#1e1e2e] bg-[#12121a] p-6 text-sm text-[#6b6b8a]">
          Loading technical indicators...
        </div>
      ) : error ? (
        <div className="rounded-xl border border-[#ff4560]/25 bg-[#ff4560]/8 p-6 text-sm text-[#ff9cab]">
          {error}
        </div>
      ) : !ticker ? (
        <div className="rounded-xl border border-[#1e1e2e] bg-[#12121a] p-6 text-sm text-[#6b6b8a]">
          Choose one of the impacted stocks above to inspect its technical setup.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {INDICATOR_ORDER.map((indicator) => (
            <IndicatorCard
              key={indicator}
              label={indicator}
              value={indicators?.[indicator]}
            />
          ))}
        </div>
      )}
    </section>
  );
}
