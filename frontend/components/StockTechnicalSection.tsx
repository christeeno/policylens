"use client";

import React from "react";
import TechnicalIndicatorPanels, { type TechnicalIndicatorsPayload } from "./TechnicalIndicatorPanels";

const API_BASE = "http://localhost:8000";

export default function StockTechnicalSection({ ticker }: { ticker?: string }) {
  const [payload, setPayload] = React.useState<TechnicalIndicatorsPayload | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!ticker) {
      setPayload(null);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;

    const loadIndicators = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_BASE}/api/stocks/${encodeURIComponent(ticker)}/indicators`);
        if (!response.ok) {
          const message = response.status === 404
            ? `Indicator data is not available for ${ticker} yet.`
            : `Failed to load indicator data for ${ticker}.`;
          throw new Error(message);
        }

        const data: TechnicalIndicatorsPayload = await response.json();
        if (!cancelled) {
          setPayload(data);
        }
      } catch (err) {
        if (!cancelled) {
          setPayload(null);
          setError(err instanceof Error ? err.message : "Unable to load indicator data.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadIndicators();

    return () => {
      cancelled = true;
    };
  }, [ticker]);

  return (
    <TechnicalIndicatorPanels
      ticker={ticker || ""}
      indicators={payload?.indicators || null}
      loading={loading}
      error={error}
      asOf={payload?.as_of}
    />
  );
}
