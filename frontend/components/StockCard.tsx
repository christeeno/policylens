"use client";

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
  const dirArrow = isPositive ? "▲" : isNegative ? "▼" : "—";
  const bgColor = isPositive ? "bg-[#00d97e]/10" : isNegative ? "bg-[#ff4560]/10" : "bg-[#a0a0b8]/10";
  
  return (
    <div className={`border border-[#1e1e2e] rounded-lg p-3 ${bgColor} flex flex-col justify-between`}>
      <div className="flex justify-between items-start mb-2">
        <div>
          <h4 className="font-mono font-bold text-[#e8e8f0] tracking-tight">{stock.ticker}</h4>
          <p className="text-[10px] text-[#6b6b8a] uppercase truncate w-32" title={stock.name}>{stock.name}</p>
        </div>
        <div className={`flex flex-col items-end ${dirColor}`}>
          <span className="text-sm font-bold">{dirArrow}</span>
        </div>
      </div>
      
      <div className="flex items-center gap-2 mb-2 mt-1">
        <span className={`text-xs font-semibold ${dirColor}`}>{stock.label}</span>
        <span className="text-[9px] bg-[#1e1e2e] text-[#a0a0b8] px-1.5 py-0.5 rounded uppercase tracking-wider">
          {stock.horizon}
        </span>
      </div>
      
      <p className="text-xs text-[#a0a0b8] italic line-clamp-2 leading-tight">
        {stock.reason}
      </p>
    </div>
  );
}
