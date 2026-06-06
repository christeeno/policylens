"use client";

import React, { useState, useEffect } from "react";
import PolicyFeed, { type PolicyItem } from "@/components/PolicyFeed";
import ValidationTab from "@/components/ValidationTab";
import ImpactReport from "@/components/ImpactReport";

const API_BASE = "http://localhost:8000";

type AnalysisReport = React.ComponentProps<typeof ImpactReport>["report"];

export default function Home() {
  const [tab, setTab] = useState<"feed" | "validation">("feed");
  const [policies, setPolicies] = useState<PolicyItem[]>([]);
  const [loadingFeed, setLoadingFeed] = useState(true);
  
  const [selectedPolicyId, setSelectedPolicyId] = useState<string | undefined>();
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/feed`)
      .then(res => res.json())
      .then(data => {
        setPolicies(data || []);
        setLoadingFeed(false);
      })
      .catch(err => {
        console.error("Failed to fetch feed:", err);
        setLoadingFeed(false);
      });
  }, []);

  const handleSelectPolicy = async (policy: PolicyItem) => {
    setSelectedPolicyId(policy.id);
    analyzeText(
      policy.full_text || policy.raw_text_preview || policy.summary || policy.title,
      policy.link,
      policy.source_type || "",
      policy.publisher || "",
      policy.article_class || "",
      policy.classification_confidence ?? null,
      policy.classification_reasoning || "",
    );
  };

  const analyzeText = async (
    text: string,
    source_url: string = "manual_input",
    source_type: string = "",
    publisher: string = "",
    article_class: string = "",
    classification_confidence: number | null = null,
    classification_reasoning: string = "",
  ) => {
    setLoadingReport(true);
    setReport(null);
    setTab("feed");
    
    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          policy_text: text,
          source_url,
          source_type,
          publisher,
          article_class,
          classification_confidence,
          classification_reasoning,
        })
      });
      const data = await res.json();
      setReport(data);
    } catch (err) {
      console.error("Analysis failed:", err);
    } finally {
      setLoadingReport(false);
    }
  };

  return (
    <main className="flex h-screen bg-[#0a0a0f] text-[#e8e8f0] overflow-hidden">
      {/* LEFT PANEL */}
      <div className="w-[35%] min-w-[350px] border-r border-[#1e1e2e] flex flex-col bg-[#0a0a0f]">
        <div className="p-4 border-b border-[#1e1e2e]">
          <h1 className="text-xl font-bold text-white mb-1">PolicyLens AI</h1>
          <p className="text-sm text-[#6b6b8a]">Autonomous Policy Analyst</p>
        </div>
        
        <div className="flex border-b border-[#1e1e2e]">
          <button 
            className={`flex-1 py-3 text-sm font-medium transition-colors ${tab === "feed" ? "text-white border-b-2 border-[#3b82f6]" : "text-[#6b6b8a] hover:text-[#e8e8f0]"}`}
            onClick={() => setTab("feed")}
          >
            Live Feed
          </button>
          <button 
            className={`flex-1 py-3 text-sm font-medium transition-colors ${tab === "validation" ? "text-white border-b-2 border-[#3b82f6]" : "text-[#6b6b8a] hover:text-[#e8e8f0]"}`}
            onClick={() => setTab("validation")}
          >
            Validation
          </button>
        </div>
        
        <div className="flex-1 overflow-hidden">
          {tab === "feed" ? (
            <PolicyFeed 
              policies={policies} 
              onSelect={handleSelectPolicy} 
              selectedId={selectedPolicyId} 
              loading={loadingFeed} 
            />
          ) : (
            <ValidationTab />
          )}
        </div>
      </div>
      
      {/* RIGHT PANEL */}
      <div className="flex-1 bg-[#0a0a0f]">
        <ImpactReport 
          report={report} 
          analyzeLoading={loadingReport} 
          onManualAnalyze={(text) => analyzeText(text)} 
        />
      </div>
    </main>
  );
}
