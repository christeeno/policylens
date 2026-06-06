"use client";

import type { StockHistoryPoint } from "@/lib/stocks";

function formatPrice(value: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(value);
}

export default function StockPriceChart({
  data,
  ticker,
}: {
  data: StockHistoryPoint[];
  ticker: string;
}) {
  if (!data.length) {
    return (
      <div className="flex h-[320px] items-center justify-center rounded-2xl border border-[#1e1e2e] bg-[#12121a] text-sm text-[#6b6b8a]">
        No chart data available for {ticker}.
      </div>
    );
  }

  const closes = data.map((point) => point.close);
  const minClose = Math.min(...closes);
  const maxClose = Math.max(...closes);
  const range = Math.max(maxClose - minClose, 1);

  const points = data
    .map((point, index) => {
      const x = (index / Math.max(data.length - 1, 1)) * 100;
      const y = 100 - ((point.close - minClose) / range) * 100;
      return `${x},${y}`;
    })
    .join(" ");

  const latest = data[data.length - 1];
  const previous = data[data.length - 2] ?? latest;
  const delta = latest.close - previous.close;
  const deltaPct = previous.close ? (delta / previous.close) * 100 : 0;
  const positive = delta >= 0;

  return (
    <section className="rounded-2xl border border-[#1e1e2e] bg-[#12121a] p-5">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-[#6b6b8a]">Price Chart</p>
          <h2 className="mt-2 font-mono text-3xl font-bold text-[#f5f7ff]">{ticker}</h2>
        </div>
        <div className="text-right">
          <p className="font-mono text-2xl font-semibold text-[#f5f7ff]">{formatPrice(latest.close)}</p>
          <p className={`text-sm ${positive ? "text-[#00d97e]" : "text-[#ff4560]"}`}>
            {positive ? "+" : ""}
            {delta.toFixed(2)} ({positive ? "+" : ""}
            {deltaPct.toFixed(2)}%)
          </p>
        </div>
      </div>

      <div className="relative h-[240px] overflow-hidden rounded-xl border border-[#232337] bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.16),_transparent_45%),linear-gradient(180deg,_rgba(255,255,255,0.02),_rgba(255,255,255,0))]">
        <div className="absolute inset-0 bg-[linear-gradient(to_bottom,transparent_24%,rgba(255,255,255,0.06)_25%,transparent_26%,transparent_49%,rgba(255,255,255,0.06)_50%,transparent_51%,transparent_74%,rgba(255,255,255,0.06)_75%,transparent_76%)]" />
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
          <polyline fill="none" stroke="#60a5fa" strokeWidth="2" points={points} vectorEffect="non-scaling-stroke" />
        </svg>
        <div className="absolute left-3 top-3 rounded-full bg-[#0f1119]/80 px-2 py-1 text-[11px] font-medium text-[#a0a0b8]">
          High {formatPrice(maxClose)}
        </div>
        <div className="absolute bottom-3 left-3 rounded-full bg-[#0f1119]/80 px-2 py-1 text-[11px] font-medium text-[#a0a0b8]">
          Low {formatPrice(minClose)}
        </div>
      </div>
    </section>
  );
}
