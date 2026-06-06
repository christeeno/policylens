"use client";

import React from "react";
import StockCard from "./StockCard";

export default function ImpactReport({ report, onManualAnalyze, analyzeLoading }: { report: any, onManualAnalyze: (text: string) => void, analyzeLoading: boolean }) {
  const [manualText, setManualText] = React.useState("");

  if (analyzeLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-[#6b6b8a]">
        <div className="w-10 h-10 border-4 border-[#3b82f6] border-t-transparent rounded-full animate-spin mb-4"></div>
        <p className="animate-pulse">Agent analyzing policy...</p>
      </div>
    );
  }

  if (!report && !analyzeLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-[#6b6b8a]">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="mb-4 opacity-50">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="3" y1="9" x2="21" y2="9"></line>
          <line x1="9" y1="21" x2="9" y2="9"></line>
        </svg>
        <p>Select a policy to analyze</p>
        
        <div className="mt-12 w-full max-w-lg">
          <p className="text-sm mb-2 opacity-70">Or manually enter policy text:</p>
          <textarea 
            className="w-full bg-[#12121a] border border-[#1e1e2e] rounded-lg p-3 text-sm text-[#e8e8f0] h-32 focus:outline-none focus:border-[#3b82f6]"
            placeholder="Paste government policy announcement here..."
            value={manualText}
            onChange={(e) => setManualText(e.target.value)}
          ></textarea>
          <button 
            onClick={() => onManualAnalyze(manualText)}
            disabled={!manualText.trim()}
            className="mt-2 w-full bg-[#3b82f6] hover:bg-[#2563eb] disabled:bg-[#1e1e2e] disabled:text-[#6b6b8a] text-white py-2 rounded-lg text-sm font-medium transition-colors"
          >
            Analyze Custom Policy
          </button>
        </div>
      </div>
    );
  }

  const confidenceColor = 
    report.confidence === "HIGH" ? "text-[#00d97e] border-[#00d97e]/30 bg-[#00d97e]/10" :
    report.confidence === "MEDIUM" ? "text-[#ffb020] border-[#ffb020]/30 bg-[#ffb020]/10" :
    "text-[#ff4560] border-[#ff4560]/30 bg-[#ff4560]/10";

  return (
    <div className="h-full overflow-y-auto p-6 flex flex-col gap-6">
      
      {/* Header Info */}
      <div className="bg-[#12121a] border border-[#1e1e2e] p-5 rounded-xl">
        <div className="flex items-center gap-3 mb-3">
          <span className="bg-[#e8e8f0] text-[#0a0a0f] text-xs font-bold px-2 py-1 rounded">
            {report.ministry}
          </span>
          <span className="border border-[#3b82f6] text-[#3b82f6] text-xs font-semibold px-2 py-1 rounded">
            {report.policy_type}
          </span>
          <div className="flex-1"></div>
          <span className="text-xs text-[#6b6b8a] font-mono">ID: {report.report_id?.substring(0,8)}</span>
        </div>
        <h2 className="text-xl font-medium text-[#e8e8f0] leading-snug mb-2">{report.key_change}</h2>
        <p className="text-sm text-[#a0a0b8] leading-relaxed">{report.policy_summary}</p>
      </div>

      {/* Sectors and Confidence */}
      <div className="flex gap-4">
        <div className="flex-1 bg-[#12121a] border border-[#1e1e2e] p-4 rounded-xl flex items-center gap-3">
          <span className="text-sm text-[#6b6b8a] w-24">Affected Sectors:</span>
          <div className="flex gap-2 flex-wrap">
            {report.sectors && report.sectors.length > 0 ? report.sectors.map((s: string) => (
              <span key={s} className="bg-[#1e1e2e] text-[#e8e8f0] text-xs px-2.5 py-1 rounded-full capitalize">
                {s.replace("_", " ")}
              </span>
            )) : <span className="text-sm text-[#a0a0b8]">None detected</span>}
          </div>
        </div>
        
        <div className="bg-[#12121a] border border-[#1e1e2e] p-4 rounded-xl flex items-center gap-3">
          <span className="text-sm text-[#6b6b8a]">Match Confidence:</span>
          <span className={`text-xs font-bold px-2 py-1 rounded border ${confidenceColor}`}>
            {report.confidence || "LOW"}
          </span>
        </div>
      </div>

      {/* Stock Watchlist */}
      <div>
        <h3 className="text-[#e8e8f0] text-sm font-semibold mb-3 tracking-wide uppercase">Top Impacted Stocks</h3>
        {report.stocks && report.stocks.length > 0 ? (
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {report.stocks.map((stock: any) => (
              <StockCard key={stock.ticker} stock={stock} />
            ))}
          </div>
        ) : (
          <div className="bg-[#12121a] border border-[#1e1e2e] p-6 rounded-xl text-center text-[#6b6b8a] text-sm">
            No specific stock impacts identified in universe.
          </div>
        )}
      </div>

      {/* Analyst Brief */}
      <div className="mt-4">
        <h3 className="text-[#e8e8f0] text-sm font-semibold mb-3 tracking-wide uppercase">Analyst Brief</h3>
        <blockquote className="border-l-4 border-[#3b82f6] pl-4 py-1 text-[#e8e8f0] text-sm leading-relaxed italic bg-[#3b82f6]/5 p-3 rounded-r-lg">
          {report.analyst_brief}
        </blockquote>
      </div>

      <div className="text-right text-[10px] text-[#6b6b8a] mt-2">
        Processed in {report.processing_time_ms}ms
      </div>
    </div>
  );
}
