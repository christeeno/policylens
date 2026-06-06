"use client";

import Link from "next/link";
import React from "react";
import StockChart from "@/components/StockChart";
import StockTechnicalSection from "@/components/StockTechnicalSection";
import { fetchStockHistory, fetchTechnicalScore, type StockHistoryResponse, type TechnicalScoreResponse } from "@/lib/stocks";

interface DetailState {
  history: StockHistoryResponse | null;
  technicalScore: TechnicalScoreResponse | null;
  loading: boolean;
  historyError: string | null;
  technicalScoreError: string | null;
}

function scoreTone(score?: number, maxScore: number = 10) {
  const normalized = typeof score === "number" ? score / maxScore : 0;
  if (normalized >= 0.7) {
    return "text-[#00d97e] border-[#00d97e]/20 bg-[#00d97e]/10";
  }
  if (normalized >= 0.4) {
    return "text-[#ffb020] border-[#ffb020]/20 bg-[#ffb020]/10";
  }
  return "text-[#ff4560] border-[#ff4560]/20 bg-[#ff4560]/10";
}

export default function StockDetailPage({ ticker }: { ticker: string }) {
  const [state, setState] = React.useState<DetailState>({
    history: null,
    technicalScore: null,
    loading: true,
    historyError: null,
    technicalScoreError: null,
  });

  React.useEffect(() => {
    let cancelled = false;

    async function load() {
      setState({
        history: null,
        technicalScore: null,
        loading: true,
        historyError: null,
        technicalScoreError: null,
      });

      const [historyResult, technicalScoreResult] = await Promise.allSettled([
        fetchStockHistory(ticker),
        fetchTechnicalScore(ticker),
      ]);

      if (cancelled) {
        return;
      }

      setState({
        history: historyResult.status === "fulfilled" ? historyResult.value : null,
        technicalScore: technicalScoreResult.status === "fulfilled" ? technicalScoreResult.value : null,
        loading: false,
        historyError:
          historyResult.status === "rejected"
            ? historyResult.reason instanceof Error
              ? historyResult.reason.message
              : "Unable to load stock data."
            : null,
        technicalScoreError:
          technicalScoreResult.status === "rejected"
            ? technicalScoreResult.reason instanceof Error
              ? technicalScoreResult.reason.message
              : "Unable to load technical score."
            : null,
      });
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [ticker]);

  if (state.loading) {
    return (
      <main className="min-h-screen bg-[#0a0a0f] px-6 py-8 text-[#e8e8f0]">
        <div className="mx-auto max-w-7xl">
          <div className="mb-6 h-6 w-40 animate-pulse rounded bg-[#171722]" />
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.8fr)]">
            <div className="h-[360px] animate-pulse rounded-2xl bg-[#12121a]" />
            <div className="space-y-6">
              <div className="h-44 animate-pulse rounded-2xl bg-[#12121a]" />
              <div className="h-64 animate-pulse rounded-2xl bg-[#12121a]" />
            </div>
          </div>
        </div>
      </main>
    );
  }

  if (!state.history && state.historyError) {
    return (
      <main className="min-h-screen bg-[#0a0a0f] px-6 py-8 text-[#e8e8f0]">
        <div className="mx-auto max-w-3xl rounded-2xl border border-[#2b1620] bg-[#1a1016] p-6">
          <Link href="/" className="text-sm text-[#60a5fa] hover:text-[#93c5fd]">
            Back to dashboard
          </Link>
          <h1 className="mt-4 text-2xl font-semibold">Unable to load {ticker}</h1>
          <p className="mt-2 text-sm text-[#c4a8b2]">{state.historyError}</p>
        </div>
      </main>
    );
  }

  const technicalScore = state.technicalScore;
  const maxScore = technicalScore?.max_score ?? 10;

  return (
    <main className="min-h-screen bg-[#0a0a0f] px-6 py-8 text-[#e8e8f0]">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <Link href="/" className="text-sm text-[#60a5fa] hover:text-[#93c5fd]">
              Back to dashboard
            </Link>
            <h1 className="mt-3 font-mono text-4xl font-bold tracking-tight text-[#f5f7ff]">{ticker}</h1>
            <p className="mt-2 text-sm text-[#6b6b8a]">
              Live stock history, technical score, and indicator panels from backend APIs.
            </p>
          </div>
          {(state.historyError || state.technicalScoreError) ? (
            <div className="rounded-full border border-[#533226] bg-[#2b1c16] px-3 py-2 text-xs text-[#ffb38a]">
              Some datasets could not be loaded. Showing available data.
            </div>
          ) : null}
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.8fr)]">
          <div className="space-y-6">
            <StockChart ticker={ticker} />
            <StockTechnicalSection ticker={ticker} />
          </div>

          <aside className="space-y-6">
            <section className="rounded-2xl border border-[#1e1e2e] bg-[#12121a] p-5">
              <p className="text-xs uppercase tracking-[0.24em] text-[#6b6b8a]">Technical Score</p>
              {technicalScore ? (
                <>
                  <div className="mt-4 flex items-end justify-between gap-4">
                    <div>
                      <p className="font-mono text-5xl font-bold text-[#f5f7ff]">{technicalScore.score}</p>
                      <p className="mt-1 text-sm text-[#6b6b8a]">out of {maxScore}</p>
                    </div>
                    <span className={`rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-[0.22em] ${scoreTone(technicalScore.score, maxScore)}`}>
                      {technicalScore.label || "Score"}
                    </span>
                  </div>
                  <p className="mt-4 text-sm leading-6 text-[#a0a0b8]">
                    {technicalScore.summary || "Technical score loaded successfully."}
                  </p>
                  {technicalScore.breakdown?.length ? (
                    <div className="mt-5 space-y-3">
                      {technicalScore.breakdown.map((item) => (
                        <div key={item.key} className="flex items-center justify-between rounded-xl border border-[#1e1e2e] bg-[#0f1119] px-3 py-2">
                          <span className="text-sm text-[#cfd3e6]">{item.label}</span>
                          <span className="font-mono text-sm text-[#f5f7ff]">{String(item.value ?? "N/A")}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="mt-4 text-sm text-[#6b6b8a]">
                  {state.technicalScoreError || `Technical score API did not return data for ${ticker}.`}
                </p>
              )}
            </section>

            <section className="rounded-2xl border border-[#1e1e2e] bg-[#12121a] p-5">
              <p className="text-xs uppercase tracking-[0.24em] text-[#6b6b8a]">Market Data Status</p>
              <div className="mt-4 space-y-3 text-sm text-[#a0a0b8]">
                <div className="flex items-center justify-between">
                  <span>Stock Data</span>
                  <span className={state.history ? "text-[#00d97e]" : "text-[#ff4560]"}>{state.history ? "Loaded" : "Unavailable"}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>History Rows</span>
                  <span className="font-mono text-[#e8e8f0]">{state.history?.ohlcv.length ?? 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Indicators</span>
                  <span className="text-[#a0a0b8]">See panel status below</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Technical Score</span>
                  <span className={technicalScore ? "text-[#00d97e]" : "text-[#ff4560]"}>{technicalScore ? "Loaded" : "Unavailable"}</span>
                </div>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
