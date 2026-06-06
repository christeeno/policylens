"use client";

import React from "react";

export interface PolicyItem {
  id: string;
  title: string;
  summary: string;
  date: string;
  link: string;
  source: string;
  source_type: string;
  publisher: string;
  article_class: string;
  classification_confidence: number;
  classification_reasoning: string;
  raw_text_preview: string;
  full_text?: string;
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

function getSourceTypeColor(sourceType: string) {
  return sourceType === "OFFICIAL"
    ? "bg-[#ffd166]/15 text-[#ffd166] border border-[#ffd166]/30"
    : "bg-[#1b2434] text-[#8ab4ff] border border-[#8ab4ff]/20";
}

function getArticleClassColor(articleClass: string) {
  switch (articleClass) {
    case "OFFICIAL_POLICY":
      return "bg-[#00d97e]/10 text-[#00d97e]";
    case "NEWS_REPORT":
      return "bg-[#3b82f6]/10 text-[#7fb0ff]";
    case "PREVIEW":
      return "bg-[#ffb020]/10 text-[#ffb020]";
    case "COMMENTARY":
      return "bg-[#ff6b6b]/10 text-[#ff8a8a]";
    case "MARKET_REACTION":
      return "bg-[#c084fc]/10 text-[#d8b4fe]";
    default:
      return "bg-[#1e1e2e] text-[#a0a0b8]";
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
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-sm ${getSourceTypeColor(p.source_type)}`}>
              {p.source_type}
            </span>
            <span className="text-xs text-[#6b6b8a]">
              {p.date ? new Date(p.date).toLocaleDateString() : "Recent"}
            </span>
          </div>
          <h3 className="text-sm text-[#e8e8f0] font-medium line-clamp-2 leading-snug">
            {p.title}
          </h3>
          <div className="mt-2 flex items-center gap-2 flex-wrap">
            <span className={`text-[10px] font-semibold px-2 py-1 rounded ${getArticleClassColor(p.article_class)}`}>
              {p.article_class}
            </span>
            <span className="text-[10px] text-[#6b6b8a] truncate max-w-[180px]">
              {p.publisher}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
