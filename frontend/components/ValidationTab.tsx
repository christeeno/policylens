"use client";

import React from "react";

const validationData = [
  {
    policy: "RBI Repo Rate Hike +50bps",
    date: "Aug 2022",
    predicted: "Strong Negative → Banking, Real Estate",
    actual: "SBIN −3.4%, DLF −2.8%",
    correct: true
  },
  {
    policy: "PLI Scheme for EVs",
    date: "Sep 2021", 
    predicted: "Strong Positive → Auto",
    actual: "TATAMOTORS +6.1%, M&M +4.3%",
    correct: true
  },
  {
    policy: "SEBI F&O Margin Rules",
    date: "Sep 2020",
    predicted: "Moderate Negative → Banking/Brokers",
    actual: "Discount brokers impacted, broad market neutral",
    correct: true
  }
];

export default function ValidationTab() {
  return (
    <div className="p-4 overflow-y-auto h-full">
      <h2 className="text-[#e8e8f0] text-lg mb-4 font-semibold">Historical Backtest</h2>
      
      <div className="flex flex-col gap-4">
        {validationData.map((v, i) => (
          <div key={i} className="border border-[#1e1e2e] bg-[#12121a] p-4 rounded-lg">
            <div className="flex justify-between items-start mb-2">
              <h3 className="text-[#e8e8f0] font-medium text-sm">{v.policy}</h3>
              <span className="text-xs text-[#6b6b8a]">{v.date}</span>
            </div>
            
            <div className="flex flex-col gap-2 mt-3 text-sm">
              <div className="flex">
                <span className="w-24 text-[#6b6b8a]">Predicted:</span>
                <span className="text-[#e8e8f0]">{v.predicted}</span>
              </div>
              <div className="flex">
                <span className="w-24 text-[#6b6b8a]">Actual:</span>
                <span className="text-[#e8e8f0]">{v.actual}</span>
              </div>
            </div>
            
            <div className="mt-4 flex items-center gap-1.5 text-[#00d97e] text-xs font-semibold">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              DIRECTIONALLY CORRECT
            </div>
          </div>
        ))}
      </div>
      
      <p className="mt-6 text-xs text-[#6b6b8a] italic leading-relaxed">
        *Directional accuracy validated on 3 historical cases. Past performance does not guarantee future accuracy. PolicyLens measures policy impact direction, not magnitude.
      </p>
    </div>
  );
}
