"use client";

import { useState, useEffect } from "react";
import { useSymbols } from "@/context/SymbolsContext";
import { Sidebar } from "@/components/Sidebar";
import ClientOnly from "@/components/ClientOnly";
import dynamic from "next/dynamic";
import {
    Play, RotateCcw, TrendingUp, BarChart3, Clock,
    Zap, Award, ChevronDown, ChevronUp, Database,
    ArrowUpRight, ArrowDownRight, Target, Trash2, RefreshCw
} from "lucide-react";

// Dynamic import for chart (SSR-incompatible)
const BacktestChart = dynamic(() => import("@/components/BacktestChart"), { ssr: false });

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

// Grade colors
const GRADE_COLORS: Record<string, string> = {
    "A+": "text-green-400 bg-green-400/10",
    "A": "text-green-500 bg-green-500/10",
    "B": "text-blue-400 bg-blue-400/10",
    "C": "text-yellow-400 bg-yellow-400/10",
    "D": "text-red-400 bg-red-400/10",
};

export default function BacktestPage() {
    const { symbols } = useSymbols();
    const [selectedSymbol, setSelectedSymbol] = useState("XAUUSD");

    const [strategies, setStrategies] = useState<any[]>([]);
    const [selectedStrategyIds, setSelectedStrategyIds] = useState<number[]>([]);

    useEffect(() => {
        const saved = localStorage.getItem("aureus_selected_symbol");
        if (saved) setSelectedSymbol(saved);
        loadStrategies();
    }, []);

    const loadStrategies = async () => {
        try {
            const res = await fetch(`${API_BASE}/strategies`);
            const data = await res.json();
            setStrategies(data);
            if (data.length > 0) setSelectedStrategyIds([data[0].id]);
        } catch { }
    };

    // Default dates: end = now, start = end - 7 days (including time)
    const now = new Date();
    const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);

    const formatDateTime = (date: Date) => {
        const pad = (n: number) => n.toString().padStart(2, '0');
        const y = date.getFullYear();
        const m = pad(date.getMonth() + 1);
        const d = pad(date.getDate());
        const h = pad(date.getHours());
        const i = pad(date.getMinutes());
        return `${y}-${m}-${d}T${h}:${i}`;
    };

    const [startDate, setStartDate] = useState(formatDateTime(weekAgo));
    const [endDate, setEndDate] = useState(formatDateTime(now));
    const [isRunning, setIsRunning] = useState(false);
    const [chartData, setChartData] = useState<any>(null);
    const [results, setResults] = useState<any>(null);
    const [runs, setRuns] = useState<any[]>([]);
    const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
    const [activeTab, setActiveTab] = useState<"chart" | "trades" | "quality">("chart");
    const [hoveredSignal, setHoveredSignal] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    // Load past runs on mount
    useEffect(() => {
        loadRuns();
    }, [selectedSymbol]);

    const loadRuns = async () => {
        try {
            const res = await fetch(`${API_BASE}/backtest/runs?symbol=${selectedSymbol}&limit=10`);
            const data = await res.json();
            setRuns(data);
        } catch { }
    };

    // Validate date range
    const validateDates = () => {
        if (!startDate || !endDate) { setError("Please select both start and end dates"); return false; }
        const startTs = new Date(startDate).getTime();
        const endTs = new Date(endDate).getTime();
        if (startTs >= endTs) { setError("Start time must be before end time"); return false; }
        const diffDays = (endTs - startTs) / (1000 * 60 * 60 * 24);
        if (diffDays > 30) { setError("Time range cannot exceed 30 days"); return false; }
        setError(null);
        return true;
    };

    // Run backtest v4 (Simulated Live)
    const runBacktest = async () => {
        if (!validateDates()) return;
        if (selectedStrategyIds.length === 0) { setError("Please select at least one strategy"); return; }

        setIsRunning(true);
        setError(null);
        setResults(null);
        setChartData(null);

        try {
            const res = await fetch(`${API_BASE}/backtest/run`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    symbol: selectedSymbol,
                    start: startDate.replace('T', ' '),
                    end: endDate.replace('T', ' '),
                    strategy_ids: selectedStrategyIds
                }),
            });
            const { task_id, error: apiError } = await res.json();

            if (apiError) {
                setError(apiError);
                setIsRunning(false);
                return;
            }

            // Poll for completion
            pollStatus(task_id);
        } catch (err: any) {
            setError(err.message);
            setIsRunning(false);
        }
    };

    const pollStatus = (taskId: string) => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/backtest/status/${taskId}`);
                const data = await res.json();

                if (data.status === "COMPLETED") {
                    clearInterval(interval);
                    await loadRuns();
                    // Load the results data
                    if (data.results && data.results.run_id) {
                        await loadRunData(data.results.run_id);
                    }
                    setIsRunning(false);
                } else if (data.status === "FAILED") {
                    clearInterval(interval);
                    setError("Backtest failed. Check logs.");
                    setIsRunning(false);
                }
            } catch {
                clearInterval(interval);
                setIsRunning(false);
            }
        }, 3000);
    };

    // Load a specific run's chart data
    const loadRunData = async (runId: number) => {
        try {
            const res = await fetch(`${API_BASE}/chart/${selectedSymbol}?run_id=${runId}`);
            const data = await res.json();
            setChartData(data);
            setResults(data);
            setSelectedRunId(runId);
        } catch (err: any) {
            setError(`Failed to load run #${runId}: ${err.message}`);
        }
    };

    return (
        <ClientOnly>
            <div className="flex bg-[#131722] min-h-screen text-gray-100 font-inter">
                <Sidebar
                    selectedSymbol={selectedSymbol}
                    onSelectSymbol={(s) => {
                        setSelectedSymbol(s);
                        localStorage.setItem("aureus_selected_symbol", s);
                    }}
                />

                <main className="flex-1 p-4 space-y-4 overflow-y-auto h-screen">
                    {/* Header */}
                    <div className="flex justify-between items-center bg-[#1E222D] p-4 rounded-xl border border-gray-800">
                        <div className="flex items-center space-x-3">
                            <div className="p-2.5 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-lg">
                                <BarChart3 className="h-5 w-5 text-blue-400" />
                            </div>
                            <div>
                                <h1 className="text-lg font-bold tracking-tight">Backtest Engine v4</h1>
                                <p className="text-xs text-gray-500">Simulated Live (Sequence-Mode) Backtesting</p>
                            </div>
                        </div>
                    </div>

                    {/* Controls Row */}
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                        {/* Left: Parameters */}
                        <div className="lg:col-span-3 bg-[#1E222D] p-4 rounded-xl border border-gray-800 space-y-4">
                            <div className="text-xs font-bold text-gray-400 uppercase tracking-widest flex items-center space-x-2">
                                <TrendingUp className="h-3.5 w-3.5" />
                                <span>Parameters</span>
                            </div>

                            <div className="space-y-3">
                                {/* Symbol Selector */}
                                <div className="space-y-1">
                                    <label className="text-[10px] text-gray-500 uppercase font-bold">Symbol</label>
                                    <select
                                        value={selectedSymbol}
                                        onChange={(e) => {
                                            setSelectedSymbol(e.target.value);
                                            localStorage.setItem("aureus_selected_symbol", e.target.value);
                                        }}
                                        className="w-full bg-[#0B0E11] border border-gray-800 rounded-lg px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-blue-500/50"
                                    >
                                        {symbols.map((s: any) => {
                                            const name = typeof s === 'string' ? s : s.name;
                                            return <option key={name} value={name}>{name}</option>;
                                        })}
                                    </select>
                                </div>

                                {/* Date/Time Range */}
                                <div className="space-y-1">
                                    <label className="text-[10px] text-gray-500 uppercase font-bold">Start Time</label>
                                    <input
                                        type="datetime-local"
                                        value={startDate}
                                        onChange={(e) => setStartDate(e.target.value)}
                                        className="w-full bg-[#0B0E11] border border-gray-800 rounded-lg px-3 py-2 text-xs outline-none focus:ring-1 focus:ring-blue-500/50"
                                    />
                                </div>

                                <div className="space-y-1">
                                    <label className="text-[10px] text-gray-500 uppercase font-bold">End Time</label>
                                    <input
                                        type="datetime-local"
                                        value={endDate}
                                        onChange={(e) => setEndDate(e.target.value)}
                                        className="w-full bg-[#0B0E11] border border-gray-800 rounded-lg px-3 py-2 text-xs outline-none focus:ring-1 focus:ring-blue-500/50"
                                    />
                                </div>

                                {/* Strategy Selector */}
                                <div className="space-y-1">
                                    <label className="text-[10px] text-gray-500 uppercase font-bold">Strategies</label>
                                    <div className="bg-[#0B0E11] border border-gray-800 rounded-lg p-2 max-h-40 overflow-y-auto space-y-1">
                                        {strategies.map((s) => (
                                            <label key={s.id} className="flex items-center space-x-2 p-1 hover:bg-gray-800/40 rounded transition-colors cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={selectedStrategyIds.includes(s.id)}
                                                    onChange={(e) => {
                                                        if (e.target.checked) setSelectedStrategyIds([...selectedStrategyIds, s.id]);
                                                        else setSelectedStrategyIds(selectedStrategyIds.filter(id => id !== s.id));
                                                    }}
                                                    className="rounded border-gray-700 bg-gray-900 text-blue-500 focus:ring-blue-500/20"
                                                />
                                                <span className="text-xs text-gray-300">{s.name}</span>
                                            </label>
                                        ))}
                                        {strategies.length === 0 && <span className="text-[10px] text-gray-500 italic px-1">Loading templates...</span>}
                                    </div>
                                </div>

                                {/* Run Button */}
                                <button
                                    onClick={runBacktest}
                                    disabled={isRunning}
                                    className={`w-full py-2.5 rounded-lg flex items-center justify-center space-x-1.5 text-xs font-bold transition-all ${isRunning
                                        ? "bg-gray-800 text-gray-500 cursor-not-allowed"
                                        : "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/20"
                                        }`}
                                >
                                    {isRunning ? <RotateCcw className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5 fill-current" />}
                                    <span>{isRunning ? "Running Sequence..." : "Run Backtest V4"}</span>
                                </button>

                                {error && (
                                    <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-xs text-red-400">
                                        {error}
                                    </div>
                                )}
                            </div>

                            {/* Past Runs */}
                            {runs.length > 0 && (
                                <div className="space-y-2">
                                    <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Past Runs</div>
                                    <div className="space-y-1 max-h-40 overflow-y-auto">
                                        {runs.map((run: any) => (
                                            <button
                                                key={run.id}
                                                onClick={() => loadRunData(run.id)}
                                                className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all ${selectedRunId === run.id
                                                    ? "bg-blue-500/20 border border-blue-500/30 text-blue-300"
                                                    : "bg-[#0B0E11] hover:bg-gray-800 text-gray-400 border border-transparent"
                                                    }`}
                                            >
                                                <div className="font-bold">#{run.id} — {run.symbol}</div>
                                                <div className="text-[10px] text-gray-500 mt-0.5">
                                                    {run.stats?.total_trades || 0} trades | {run.stats?.win_rate?.toFixed(1) || 0}% WR
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Right: Results Area */}
                        <div className="lg:col-span-9 space-y-4">
                            {!chartData ? (
                                <div className="h-[600px] flex flex-col items-center justify-center bg-[#0B0E11]/40 border-2 border-dashed border-gray-800 rounded-xl p-12 text-center">
                                    <div className="p-5 bg-gray-800/10 rounded-full mb-4">
                                        <Clock className="h-10 w-10 text-gray-700" />
                                    </div>
                                    <h3 className="text-lg font-bold text-gray-400 mb-1">No Results Yet</h3>
                                    <p className="text-xs text-gray-500 max-w-sm leading-relaxed">
                                        Pre-compute signals first, then run a backtest to see chart visualization with signal markers and trade analysis.
                                    </p>
                                </div>
                            ) : (
                                <>
                                    {/* Stats Cards */}
                                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                                        <StatCard label="Total Trades" value={results?.stats?.total_trades || 0} />
                                        <StatCard
                                            label="Win Rate"
                                            value={`${(results?.stats?.win_rate || 0).toFixed(1)}%`}
                                            color={results?.stats?.win_rate >= 50 ? "text-green-400" : "text-red-400"}
                                        />
                                        <StatCard
                                            label="Net PnL"
                                            value={results?.stats?.total_pnl?.toFixed(2) || "0"}
                                            color={results?.stats?.total_pnl >= 0 ? "text-blue-400" : "text-red-400"}
                                            prefix={results?.stats?.total_pnl >= 0 ? "+" : ""}
                                        />
                                        <StatCard
                                            label="Best Trade"
                                            value={results?.stats?.best_trade?.toFixed(2) || "—"}
                                            color="text-green-400"
                                            prefix="+"
                                        />
                                        <StatCard
                                            label="Worst Trade"
                                            value={results?.stats?.worst_trade?.toFixed(2) || "—"}
                                            color="text-red-400"
                                        />
                                    </div>

                                    {/* Tab Navigation */}
                                    <div className="flex space-x-1 bg-[#1E222D] rounded-lg p-1 border border-gray-800">
                                        {(["chart", "trades", "quality"] as const).map(tab => (
                                            <button
                                                key={tab}
                                                onClick={() => setActiveTab(tab)}
                                                className={`flex-1 py-2 rounded-md text-xs font-bold uppercase tracking-wider transition-all ${activeTab === tab
                                                    ? "bg-blue-500/20 text-blue-300"
                                                    : "text-gray-500 hover:text-gray-300"
                                                    }`}
                                            >
                                                {tab === "chart" && <span>📊 Chart</span>}
                                                {tab === "trades" && <span>📋 Trades ({results?.trades?.length || 0})</span>}
                                                {tab === "quality" && <span>🏆 Signal Quality</span>}
                                            </button>
                                        ))}
                                    </div>

                                    {/* Tab Content */}
                                    {activeTab === "chart" && (
                                        <BacktestChart
                                            candles={chartData.candles || []}
                                            signalEvents={chartData.signal_events || []}
                                            trades={chartData.trades || []}
                                            equityCurve={chartData.equity_curve || []}
                                            swingPoints={chartData.swing_points || []}
                                            obs={chartData.obs || []}
                                            digits={chartData.digits || 2}
                                            onEventHover={setHoveredSignal}
                                        />
                                    )}

                                    {activeTab === "trades" && (
                                        <div className="bg-[#1E222D] rounded-xl border border-gray-800 overflow-hidden">
                                            <div className="max-h-[500px] overflow-y-auto">
                                                <table className="w-full text-sm text-left">
                                                    <thead className="text-[10px] text-gray-500 uppercase bg-[#0B0E11]/60 border-b border-gray-800 sticky top-0">
                                                        <tr>
                                                            <th className="px-4 py-3 font-bold">Strategy</th>
                                                            <th className="px-4 py-3 font-bold">Side</th>
                                                            <th className="px-4 py-3 font-bold">Entry</th>
                                                            <th className="px-4 py-3 font-bold">Exit</th>
                                                            <th className="px-4 py-3 font-bold">Reason</th>
                                                            <th className="px-4 py-3 font-bold">PnL</th>
                                                            <th className="px-4 py-3 font-bold">Session</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody className="divide-y divide-gray-800/50">
                                                        {(results?.trades || []).map((t: any, i: number) => (
                                                            <tr key={i} className="hover:bg-gray-800/20 transition-colors">
                                                                <td className="px-4 py-3 font-bold text-gray-300 text-xs">{t.strategy_name}</td>
                                                                <td className="px-4 py-3">
                                                                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${t.side === 'BUY' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                                                                        {t.side === 'BUY' ? <ArrowUpRight className="inline h-3 w-3" /> : <ArrowDownRight className="inline h-3 w-3" />}
                                                                        {" "}{t.side}
                                                                    </span>
                                                                </td>
                                                                <td className="px-4 py-3 font-mono text-xs text-gray-400">
                                                                    {t.entry_price?.toFixed(chartData.digits || 2)}
                                                                </td>
                                                                <td className="px-4 py-3 font-mono text-xs text-gray-400">
                                                                    {t.exit_price?.toFixed(chartData.digits || 2) || "—"}
                                                                </td>
                                                                <td className="px-4 py-3 text-xs">
                                                                    <span className={`font-bold ${t.exit_reason === 'TP' ? 'text-green-400' : t.exit_reason === 'SL' ? 'text-red-400' : 'text-gray-500'}`}>
                                                                        {t.exit_reason || "—"}
                                                                    </span>
                                                                </td>
                                                                <td className={`px-4 py-3 font-bold font-mono text-xs ${t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                                    {t.pnl > 0 ? '+' : ''}{t.pnl?.toFixed(4)}
                                                                </td>
                                                                <td className="px-4 py-3 text-[10px] text-gray-500">
                                                                    {t.signal_context?.session || "—"}
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    )}

                                    {activeTab === "quality" && (
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                            {(results?.signal_quality || []).map((sq: any) => (
                                                <div key={sq.tag} className="bg-[#1E222D] p-4 rounded-xl border border-gray-800">
                                                    <div className="flex justify-between items-start mb-3">
                                                        <div>
                                                            <div className="text-sm font-bold text-gray-200">{sq.tag}</div>
                                                            <div className="text-[10px] text-gray-500 mt-0.5">{sq.count} occurrences</div>
                                                        </div>
                                                        <div className={`px-2.5 py-1 rounded-lg text-xs font-black ${GRADE_COLORS[sq.grade] || "text-gray-400 bg-gray-400/10"}`}>
                                                            {sq.grade}
                                                        </div>
                                                    </div>

                                                    <div className="grid grid-cols-3 gap-2">
                                                        <div>
                                                            <div className="text-[10px] text-gray-500 uppercase">Win Rate</div>
                                                            <div className={`text-sm font-bold ${sq.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                                                                {sq.win_rate}%
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <div className="text-[10px] text-gray-500 uppercase">Trade Rate</div>
                                                            <div className="text-sm font-bold text-blue-400">{sq.trade_rate}%</div>
                                                        </div>
                                                        <div>
                                                            <div className="text-[10px] text-gray-500 uppercase">Avg PnL</div>
                                                            <div className={`text-sm font-bold font-mono ${sq.avg_pips >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                                {sq.avg_pips >= 0 ? '+' : ''}{sq.avg_pips}
                                                            </div>
                                                        </div>
                                                    </div>

                                                    <div className="mt-3 flex rounded-full h-1.5 overflow-hidden bg-gray-800">
                                                        <div className="bg-green-500 transition-all" style={{ width: `${sq.win_rate}%` }} />
                                                        <div className="bg-red-500 transition-all" style={{ width: `${100 - sq.win_rate}%` }} />
                                                    </div>
                                                </div>
                                            ))}

                                            {(!results?.signal_quality || results.signal_quality.length === 0) && (
                                                <div className="col-span-2 text-center py-12 text-gray-500 text-sm">
                                                    No signal quality data available for this backtest run.
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                </main>
            </div>
        </ClientOnly>
    );
}

// Stat card mini-component
function StatCard({ label, value, color = "text-white", prefix = "" }: {
    label: string; value: string | number; color?: string; prefix?: string;
}) {
    return (
        <div className="bg-[#1E222D] px-4 py-3 rounded-xl border border-gray-800">
            <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-1">{label}</div>
            <div className={`text-xl font-bold ${color}`}>{prefix}{value}</div>
        </div>
    );
}
