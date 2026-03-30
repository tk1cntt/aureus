"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import ClientOnly from "@/components/ClientOnly";
import { BrainCircuit, ShieldCheck, ShieldAlert, BarChart3, TrendingUp, TrendingDown, Info, Clock } from "lucide-react";
import { InstitutionalAudit, ModelSelector } from "@/components/AIInsights";

interface AiAudit {
    aci: number;
    decision: string;
    key_insight: string;
    debate_log: {
        trend: string;
        liquidity: string;
        assassin: string;
        judgement: string;
        monologue?: string;
    };
    llm_latency_ms?: number;
    prompt_tokens?: number;
    completion_tokens?: number;
    request_payload?: string;
    response_payload?: string;
}

interface SimulatedOrder {
    trace_id: string;
    side: "BUY" | "SELL";
    symbol: string;
    strategy_name: string;
    entry_price: number;
    ai_audit?: AiAudit;
}

interface SmcState {
    simulated_orders?: SimulatedOrder[];
}

interface AiHealth {
    status?: "ONLINE" | "OFFLINE" | string;
}

interface AiHistoryItem {
    time: number;
    analysis_type?: string;
    decision?: string;
    sentiment?: string;
    aci: number;
    key_insight?: string;
    narrative?: string;
    debate_log: {
        trend: string;
        liquidity: string;
        assassin: string;
        judgement: string;
        monologue?: string;
    };
    llm_latency_ms?: number;
    prompt_tokens?: number;
    completion_tokens?: number;
    request_payload?: string;
    response_payload?: string;
}

interface AiLatest {
    aci?: number;
}

export default function AIInsightsPage() {
    const [selectedSymbol, setSelectedSymbol] = useState<string>("");
    const [smcState, setSmcState] = useState<SmcState | null>(null);
    const [aiAnalysis, setAiAnalysis] = useState<AiLatest | null>(null);
    const [aiHistory, setAiHistory] = useState<AiHistoryItem[]>([]);
    const [aiHealth, setAiHealth] = useState<AiHealth | null>(null);
    const [loading, setLoading] = useState(true);

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

    // 0. Initialize from localStorage
    useEffect(() => {
        const saved = localStorage.getItem("aureus_selected_symbol");
        setSelectedSymbol(saved || "XAUUSD");
    }, []);

    useEffect(() => {
        if (!selectedSymbol) return;
        setLoading(true);

        const fetchData = async () => {
            try {
                const [stateRes, healthRes, aiRes, historyRes] = await Promise.all([
                    fetch(`${API_BASE}/state/${selectedSymbol}`),
                    fetch(`${API_BASE}/ai/health`),
                    fetch(`${API_BASE}/ai/latest/${selectedSymbol}`),
                    fetch(`${API_BASE}/ai/history/${selectedSymbol}`)
                ]);
                const sData = (await stateRes.json()) as SmcState;
                const hData = (await healthRes.json()) as AiHealth;
                const aiData = aiRes.ok ? ((await aiRes.json()) as AiLatest) : null;
                const histData = historyRes.ok ? ((await historyRes.json()) as AiHistoryItem[]) : [];

                setSmcState(sData);
                setAiHealth(hData);
                setAiAnalysis(aiData);
                setAiHistory(histData);
            } catch (err) {
                console.error("Data fetch error", err);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
        const interval = setInterval(fetchData, 3000);
        return () => clearInterval(interval);
    }, [selectedSymbol, API_BASE]);

    // Aggregate Stats
    const allAudits = (smcState?.simulated_orders?.filter((o) => o.ai_audit) ?? []) as (SimulatedOrder & { ai_audit: AiAudit })[];
    const approved = allAudits.filter((o) => o.ai_audit.decision !== "REJECTED");
    const rejected = allAudits.filter((o) => o.ai_audit.decision === "REJECTED");
    const avgAci = Number(aiAnalysis?.aci || 0);

    return (
        <ClientOnly>
            <div className="flex bg-[#131722] min-h-screen text-gray-100 font-inter">
                <Sidebar
                    selectedSymbol={selectedSymbol}
                    onSelectSymbol={(s) => {
                        setSelectedSymbol(s);
                        localStorage.setItem("aureus_selected_symbol", s);
                    }}
                    isConnected={!loading}
                />

                <main className="flex-1 p-6 overflow-y-auto">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-8">
                        <div className="flex items-center space-x-4">
                            <div className="p-3 bg-amber-500/10 rounded-xl">
                                <BrainCircuit className="h-8 w-8 text-amber-500" />
                            </div>
                            <div>
                                <div className="flex items-center space-x-4">
                                    <h1 className="text-2xl font-black text-white">AI Institutional Intelligence</h1>
                                    <ModelSelector />
                                </div>
                                <div className="flex items-center space-x-3 mt-1">
                                    <p className="text-gray-500 text-sm">DeepSeek-R1 Multi-Agent Reasoning</p>
                                    <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/20">
                                        <div className={`w-1.5 h-1.5 rounded-full ${aiHealth?.status === 'ONLINE' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                                        <span className={`text-[10px] font-bold uppercase ${aiHealth?.status === 'ONLINE' ? 'text-green-500' : 'text-red-500'}`}>
                                            {aiHealth?.status === 'ONLINE' ? 'Operational' : 'Offline'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center space-x-6">
                            <StatBox label="Avg ACI" value={`${avgAci.toFixed(1)}%`} icon={<BarChart3 className="h-4 w-4 text-blue-500" />} />
                            <StatBox label="Sanctioned" value={approved.length} icon={<ShieldCheck className="h-4 w-4 text-green-500" />} />
                            <StatBox label="Rejected" value={rejected.length} icon={<ShieldAlert className="h-4 w-4 text-red-500" />} />
                        </div>
                    </div>

                    <div className="max-w-4xl">
                        {/* Audit Feed */}
                        <div className="space-y-4">
                            <h2 className="text-sm font-bold text-gray-400 uppercase tracking-widest px-1">Institutional Audit Feed</h2>

                            {allAudits.length > 0 ? (
                                [...allAudits].reverse().map((order) => (
                                    <div key={order.trace_id} className="bg-[#1E222D] border border-gray-800 rounded-2xl p-4 shadow-xl">
                                        <div className="flex justify-between items-center mb-2">
                                            <div className="flex items-center space-x-3">
                                                <div className={`p-1.5 rounded-lg ${order.side === 'BUY' ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}`}>
                                                    <TrendingUp className={`h-3.5 w-3.5 ${order.side === 'SELL' ? 'rotate-180' : ''}`} />
                                                </div>
                                                <div>
                                                    <div className="text-xs font-bold text-gray-200">{order.strategy_name}</div>
                                                    <div className="text-[9px] text-gray-500 uppercase font-mono flex items-center space-x-2">
                                                        <span>{order.symbol} • {order.side} • @{order.entry_price.toFixed(5)}</span>
                                                        {order.ai_audit.llm_latency_ms && (
                                                            <div className="flex items-center space-x-2 border-l border-gray-800 pl-2 ml-2">
                                                                <span className="opacity-70 whitespace-nowrap text-[8px] text-gray-400">DR1 Op</span>
                                                                <span className="px-1.5 py-0.5 rounded bg-gray-900 border border-gray-800 text-gray-300 text-[8px]">{order.ai_audit.llm_latency_ms}ms</span>
                                                                 <span className="text-[8px] opacity-70 whitespace-nowrap text-gray-400">{(order.ai_audit.prompt_tokens ?? 0) + (order.ai_audit.completion_tokens ?? 0)} tokens</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="flex items-center space-x-2">
                                                <span className={`text-lg font-black ${order.ai_audit.decision === 'REJECTED' ? 'text-red-500' : 'text-green-500'}`}>
                                                    {order.ai_audit.aci}
                                                </span>
                                                {order.ai_audit.decision === 'REJECTED' ? (
                                                    <TrendingDown className="h-4 w-4 text-red-500" />
                                                ) : (
                                                    <TrendingUp className="h-4 w-4 text-green-500" />
                                                )}
                                            </div>
                                        </div>

                                        <InstitutionalAudit audit={order.ai_audit} />
                                    </div>
                                ))
                            ) : aiHistory.length > 0 ? (
                                aiHistory.map((hist, idx: number) => (
                                    <div key={`${hist.time}-${idx}`} className="bg-[#1E222D]/60 border border-gray-800/50 rounded-2xl p-4 shadow-lg">
                                        <div className="flex justify-between items-center mb-2">
                                            <div className="flex items-center space-x-3">
                                                <div className={`p-1.5 rounded-lg ${hist.analysis_type === 'PULSE' ? 'bg-purple-500/10 text-purple-400' : 'bg-gray-800/50 text-gray-400'}`}>
                                                    {hist.analysis_type === 'PULSE' ? <BrainCircuit className="h-3.5 w-3.5" /> : <Clock className="h-3.5 w-3.5" />}
                                                </div>
                                                <div>
                                                    <div className="text-xs font-bold text-gray-400">{hist.analysis_type === 'PULSE' ? 'Institutional Pulse' : 'Historical Audit'}</div>
                                                    <div className="text-[9px] text-gray-600 uppercase font-mono flex items-center space-x-2">
                                                        <span>{new Date(hist.time * 1000).toLocaleString()}</span>
                                                        {hist.llm_latency_ms && (
                                                            <div className="flex items-center space-x-2 border-l border-gray-800 pl-2 ml-2">
                                                                <span className="opacity-70 whitespace-nowrap text-[8px] text-gray-400">DR1 Op</span>
                                                                <span className="px-1.5 py-0.5 rounded bg-gray-900 border border-gray-800 text-gray-300 text-[8px]">{hist.llm_latency_ms}ms</span>
                                                                 <span className="text-[8px] opacity-70 whitespace-nowrap text-gray-400">{(hist.prompt_tokens ?? 0) + (hist.completion_tokens ?? 0)} tokens</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="flex items-center space-x-2">
                                                <span className={`text-lg font-black ${hist.decision === 'REJECTED' || hist.sentiment === 'BEARISH' ? 'text-red-500' : 'text-green-500'}`}>
                                                    {hist.aci}
                                                </span>
                                                {hist.decision === 'REJECTED' || hist.sentiment === 'BEARISH' ? (
                                                    <TrendingDown className="h-4 w-4 text-red-500" />
                                                ) : (
                                                    <TrendingUp className="h-4 w-4 text-green-500" />
                                                )}
                                            </div>
                                        </div>

                                        <InstitutionalAudit audit={{
                                            aci: hist.aci,
                                            decision: hist.decision ?? hist.sentiment ?? "UNKNOWN",
                                            key_insight: hist.key_insight ?? hist.narrative ?? "",
                                            debate_log: hist.debate_log,
                                            llm_latency_ms: hist.llm_latency_ms,
                                            prompt_tokens: hist.prompt_tokens,
                                            completion_tokens: hist.completion_tokens,
                                            request_payload: hist.request_payload,
                                            response_payload: hist.response_payload
                                        }} />
                                    </div>
                                ))
                            ) : (
                                <div className="p-20 flex flex-col items-center justify-center border border-dashed border-gray-800 rounded-3xl bg-gray-900/10 text-center">
                                    <Info className="h-10 w-10 text-gray-700 mb-4" />
                                    <p className="text-gray-500 font-medium text-sm">No institutional audits performed yet.</p>
                                </div>
                            )}
                        </div>
                    </div>
                </main>
            </div>
        </ClientOnly>
    );
}

function StatBox({ label, value, icon }: { label: string, value: string | number, icon: React.ReactNode }) {
    return (
        <div className="flex flex-col items-end">
            <div className="flex items-center space-x-2 text-xs font-bold text-gray-500 uppercase tracking-tighter">
                {icon}
                <span>{label}</span>
            </div>
            <div className="text-xl font-black text-white">{value}</div>
        </div>
    );
}
