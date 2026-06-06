"use client";

import Link from "next/link";
import React from "react";

interface Stock {
  ticker: string;
  name: string;
  sector: string;
  direction: string;
  score: number;
  label: string;
  horizon: string;
  reason: string;
}

export default function StockCard({ stock }: { stock: Stock }) {
  const isPositive = stock.direction === "POSITIVE";
  const isNegative = stock.direction === "NEGATIVE";

  const dirColor = isPositive ? "text-[#00d97e]" : isNegative ? "text-[#ff4560]" : "text-[#a0a0b8]";
  const dirArrow = isPositive ? "+" : isNegative ? "-" : "~";
  const bgColor = isPositive ? "bg-[#00d97e]/10" : isNegative ? "bg-[#ff4560]/10" : "bg-[#a0a0b8]/10";

  return (
    <Link
      href={`/stocks/${encodeURIComponent(stock.ticker)}`}
      className={`flex w-full flex-col justify-between rounded-lg border border-[#1e1e2e] p-3 text-left transition-all hover:-translate-y-0.5 hover:border-[#3b82f6]/60 hover:bg-[#171b2a] focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/50 ${bgColor}`}
    >
      <div className="mb-2 flex items-start justify-between">
        <div>
          <h4 className="font-mono font-bold tracking-tight text-[#e8e8f0]">{stock.ticker}</h4>
          <p className="w-32 truncate text-[10px] uppercase text-[#6b6b8a]" title={stock.name}>
            {stock.name}
          </p>
        </div>
        <div className={`flex flex-col items-end ${dirColor}`}>
          <span className="text-sm font-bold">{dirArrow}</span>
        </div>
      </div>

      <div className="mb-2 mt-1 flex items-center gap-2">
        <span className={`text-xs font-semibold ${dirColor}`}>{stock.label}</span>
        <span className="rounded bg-[#1e1e2e] px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-[#a0a0b8]">
          {stock.horizon}
        </span>
      </div>

      <p className="line-clamp-2 text-xs italic leading-tight text-[#a0a0b8]">{stock.reason}</p>
    </Link>
  );
}
