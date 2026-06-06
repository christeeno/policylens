"use client";

import React from "react";

interface PolicyItem {
  id: string;
  title: string;
  summary: string;
  date: string;
  link: string;
  source: string;
}

interface Props {
  policies: PolicyItem[];
  onSelect: (policy: PolicyItem) => void;
  selectedId?: string;
  loading: boolean;
}

function getSourceColor(source: string) {
  switch (source.toUpperCase()) {
    case "RBI":
      return "bg-[#ff6b35] text-white";
    case "SEBI":
      return "bg-[#3b82f6] text-white";
    case "PIB":
      return "bg-[#10b981] text-white";
    default:
      return "bg-gray-600 text-white";
  }
}

export default function PolicyFeed({ policies, onSelect, selectedId, loading }: Props) {
  if (loading) {
    return (
      <div className="flex flex-col gap-3 p-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="animate-pulse bg-[#1e1e2e] h-20 rounded-md"></div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 p-4 overflow-y-auto h-full hide-scrollbar">
      {policies.map((p) => (
        <div
          key={p.id}
          onClick={() => onSelect(p)}
          className={`cursor-pointer border border-[#1e1e2e] p-3 rounded-lg transition-colors duration-200 ${
            selectedId === p.id ? "bg-[#1e1e2e] border-[#6b6b8a]" : "bg-[#12121a] hover:bg-[#1e1e2e]"
          }`}
        >
          <div className="flex items-center gap-2 mb-2">
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-sm ${getSourceColor(p.source)}`}>
              {p.source}
            </span>
            <span className="text-xs text-[#6b6b8a]">
              {new Date(p.date).toLocaleDateString()}
            </span>
          </div>
          <h3 className="text-sm text-[#e8e8f0] font-medium line-clamp-2 leading-snug">
            {p.title}
          </h3>
        </div>
      ))}
    </div>
  );
}
