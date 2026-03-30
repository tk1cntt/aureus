"use client";

import { useEffect, useState } from "react";
import { useSymbols } from "@/context/SymbolsContext";
import { Sidebar } from "@/components/Sidebar";
import { SMCChart } from "@/components/SMCChart";
import { ConfluenceOverlay } from "@/components/ConfluenceOverlay";
import ClientOnly from "@/components/ClientOnly";
import { Activity, Zap, Settings, RefreshCw, BrainCircuit, Clock } from "lucide-react";
import { InstitutionalAudit } from "@/components/AIInsights";
import { MarketPulse } from "@/components/MarketPulse";

interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface SwingPoint {
  t: number;
  price: number;
  breakout_t?: number | null;
  is_high?: boolean;
  type?: string;
  is_choch?: boolean;
  choch_type?: string;
}

interface OrderBlock {
  ob_type?: string;
  top?: number;
  bottom?: number;
  t_start?: number | null;
  t_mitigation?: number | null;
  capped_time?: number | null;
}

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
  status: string;
  strategy_name: string;
  side: "BUY" | "SELL";
  entry_price: number;
  sl: number;
  tp: number;
  ai_audit?: AiAudit;
}

interface StepProgress {
  tag: string;
  weight: number;
  required: boolean;
  status: "matched" | "waiting" | "missed";
  time?: number;
}

interface StrategyProgress {
  strategy: string;
  progress_pct: number;
  sequence: StepProgress[];
}

interface ClosedOrder {
  trace_id: string;
  strategy_name: string;
  close_time: number;
  pnl: number;
  ai_audit?: AiAudit;
}

interface SmcState {
  obs?: OrderBlock[];
  strategy_progress?: Record<string, StrategyProgress>;
  simulated_orders?: SimulatedOrder[];
  active_orders?: SimulatedOrder[];
  closed_orders?: ClosedOrder[];
  swing_points?: SwingPoint[];
}

interface ChartApiData {
  candles?: Candle[];
  swing_points?: SwingPoint[];
  digits?: number;
}

interface AiAnalysis {
  narrative: string;
  sentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  aci: number;
  timestamp: number;
  debate_log?: {
    trend: string;
    liquidity: string;
    skeptic: string;
    monologue?: string;
  };
  prompt_tokens?: number;
  completion_tokens?: number;
  llm_latency_ms?: number;
  total_latency_ms?: number;
}

export default function DashboardPage() {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);

  // 0. Initialize selected symbol from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("aureus_selected_symbol");
    if (saved) {
      setSelectedSymbol(saved);
    } else {
      setSelectedSymbol("XAUUSD");
    }
  }, []);
  const [chartData, setChartData] = useState<Candle[]>([]);
  const [smcState, setSmcState] = useState<SmcState | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<AiAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [precision, setPrecision] = useState(2);
  const { symbols: allSymbols } = useSymbols();
  const [chartType, setChartType] = useState<"candles" | "line">("candles");
  const [showSettings, setShowSettings] = useState(false);
  const [isRecovering, setIsRecovering] = useState(false);
  const [settings, setSettings] = useState({
    lineColor: "#2962FF",
    zigzagColor: "#2962FF",
    bullishOBColor: "#00FF00",
    bearishOBColor: "#FF0000",
    showLabels: false,
    showZigzag: false,
    showOB: true,
    showCHOCH: true,
    visibleBars: 150,
  });

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

  // 0. Load settings from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("aureus_chart_settings");
    if (saved) {
      try {
        setSettings(prev => ({ ...prev, ...JSON.parse(saved) }));
      } catch (e) {
        console.error("Failed to parse saved settings", e);
      }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("aureus_chart_settings", JSON.stringify(settings));
  }, [settings]);


  // 1b. Proactively set precision whenever selectedSymbol changes
  useEffect(() => {
    if (selectedSymbol && allSymbols.length > 0) {
      const symObj = allSymbols.find(s => s.name === selectedSymbol);
      if (symObj && symObj.digits !== undefined) {
        setPrecision(symObj.digits);
      }
    }
  }, [selectedSymbol, allSymbols]);

  const handleForceRecovery = async () => {
    if (!selectedSymbol) return;
    setIsRecovering(true);
    try {
      const res = await fetch(`${API_BASE}/symbols/${selectedSymbol}/recover`, { method: "POST" });
      if (!res.ok) throw new Error("Recovery failed");
      // Keep loading state for 2s to give feedback
      setTimeout(() => setIsRecovering(false), 2000);
    } catch (err) {
      console.error("Force recovery error:", err);
      setIsRecovering(false);
    }
  };


  // 2. Fetch chart data + state for selected symbol
  useEffect(() => {
    if (!selectedSymbol) return;
    setLoading(true);

    const GMT7_OFFSET = 7 * 3600; // +7 hours in seconds

    const fetchData = async () => {
      try {
        const [chartRes, stateRes, aiRes] = await Promise.all([
          fetch(`${API_BASE}/chart/${selectedSymbol}`),
          fetch(`${API_BASE}/state/${selectedSymbol}`),
          fetch(`${API_BASE}/ai/latest/${selectedSymbol}`)
        ]);

        const cData = (await chartRes.json()) as ChartApiData;
        const sData = (await stateRes.json()) as SmcState;
        const aiData = aiRes.ok ? ((await aiRes.json()) as AiAnalysis) : null;

        // Shift all timestamps to GMT+7 for chart display
        const shiftedCandles = (cData.candles || []).map((c) => ({
          ...c,
          time: c.time + GMT7_OFFSET,
        }));

        const shiftedSwingPoints = (cData.swing_points || []).map((sp) => ({
          ...sp,
          t: sp.t + GMT7_OFFSET,
          ...(sp.breakout_t != null ? { breakout_t: sp.breakout_t + GMT7_OFFSET } : {}),
        }));

        const shiftedObs = (sData.obs || []).map((ob) => ({
          ...ob,
          t_start: ob.t_start != null ? ob.t_start + GMT7_OFFSET : ob.t_start,
          t_mitigation: ob.t_mitigation != null ? ob.t_mitigation + GMT7_OFFSET : ob.t_mitigation,
          capped_time: ob.capped_time != null ? ob.capped_time + GMT7_OFFSET : ob.capped_time,
        }));

        setChartData(shiftedCandles);
        setAiAnalysis(aiData);
        if (cData.digits !== undefined) {
          setPrecision(cData.digits);
        }

        // Inject the comprehensive db+redis swing points into the state object for the chart
        const unifiedState = {
          ...sData,
          swing_points: shiftedSwingPoints,
          obs: shiftedObs,
        };
        setSmcState(unifiedState);
      } catch (err) {
        console.error("Fetch error:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    // Polling for real-time updates every 2 seconds
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, [selectedSymbol, API_BASE]);

  if (!selectedSymbol) {
    return (
      <div className="flex bg-[#0B0E11] text-[#D9D9D9] h-screen items-center justify-center">
        <div className="flex flex-col items-center space-y-4">
          <RefreshCw className="h-8 w-8 animate-spin text-blue-500" />
          <span className="text-sm font-medium animate-pulse">Initializing Aureus...</span>
        </div>
      </div>
    );
  }

  return (
    <ClientOnly>
      <div className="flex bg-[#131722] min-h-screen text-gray-100 font-inter" suppressHydrationWarning>
        <Sidebar
          selectedSymbol={selectedSymbol}
          onSelectSymbol={setSelectedSymbol}
          isConnected={!loading}
        />

        <main className="flex-1 p-4 flex flex-col space-y-4 h-screen overflow-hidden" suppressHydrationWarning>
          {/* Header */}
          <div className="flex justify-between items-center bg-[#1E222D] p-3 rounded-xl border border-gray-800 shadow-md" suppressHydrationWarning>
            <div className="flex items-center space-x-3">
              <div className="p-2.5 bg-blue-500/10 rounded-lg">
                <Activity className="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <div className="text-xl font-bold leading-none">{selectedSymbol}</div>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <div className="flex bg-[#0B0E11] px-1 py-1 rounded-lg border border-gray-800">
                <button
                  onClick={() => setChartType("candles")}
                  className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all flex items-center space-x-2 ${chartType === "candles"
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-900/20"
                    : "text-gray-400 hover:text-gray-200"
                    }`}
                >
                  <Activity className="h-4 w-4" />
                  <span>Candles</span>
                </button>
                <button
                  onClick={() => setChartType("line")}
                  className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all flex items-center space-x-2 ${chartType === "line"
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-900/20"
                    : "text-gray-400 hover:text-gray-200"
                    }`}
                >
                  <Zap className="h-4 w-4" />
                  <span>Line</span>
                </button>
              </div>

              <button
                onClick={handleForceRecovery}
                disabled={isRecovering}
                title="Force Data Recovery (1 hour)"
                className={`p-2.5 bg-[#0B0E11] text-gray-400 hover:text-white rounded-lg border border-gray-800 transition-colors ${isRecovering ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-800'}`}
                suppressHydrationWarning
              >
                <RefreshCw className={`h-5 w-5 ${isRecovering ? 'animate-spin text-amber-500' : ''}`} />
              </button>

              <button
                onClick={() => setShowSettings(true)}
                className="p-2.5 bg-[#0B0E11] text-gray-400 hover:text-white rounded-lg border border-gray-800 hover:bg-gray-800 transition-colors"
                suppressHydrationWarning
              >
                <Settings className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* 2-Column Split */}
          <div className="flex-1 flex space-x-4 min-h-0" suppressHydrationWarning>
            {/* Left: Chart */}
            <div className="flex-1 bg-[#0B0E11] rounded-xl border border-gray-800 overflow-hidden relative shadow-lg" suppressHydrationWarning>
              {loading && chartData.length === 0 ? (
                <div className="absolute inset-0 flex items-center justify-center bg-[#0B0E11]/80 z-10 backdrop-blur-sm" suppressHydrationWarning>
                  <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500" suppressHydrationWarning></div>
                </div>
              ) : (
                <SMCChart
                  symbol={selectedSymbol}
                  data={chartData}
                  smcState={smcState ?? {}}
                  chartType={chartType}
                  settings={settings}
                  precision={precision}
                />
              )}
            </div>

            {/* Right: Strategy Tracker */}
            <div className="w-80 flex flex-col space-y-3 overflow-y-auto pr-1 pb-4" suppressHydrationWarning>
              {/* Active Monitoring */}
              <div className="text-xs font-bold text-gray-500 uppercase tracking-wider px-1">
                Active Monitoring
              </div>
              {smcState?.strategy_progress && Object.keys(smcState.strategy_progress).length > 0 ? (
                <ConfluenceOverlay progressData={smcState.strategy_progress} />
              ) : (
                <div className="text-sm text-gray-500 italic p-4 text-center border border-dashed border-gray-800 rounded-xl bg-[#1E222D]/50">
                  No active strategies triggering.
                </div>
              )}

              {/* MarketPulse Narrative Section */}
              <div className="mt-4 mb-6">
                <MarketPulse analysis={aiAnalysis} />
              </div>

              {/* Pending AI Verification */}
              {smcState?.simulated_orders?.some((o) => o.status === 'PENDING_AI') && (
                <>
                  <div className="text-xs font-bold text-amber-500 uppercase tracking-wider px-1 mt-4 flex items-center space-x-2">
                    <Clock className="h-3 w-3 animate-pulse" />
                    <span>Pending AI Audit</span>
                  </div>
                  <div className="space-y-2 mt-2">
                    {smcState.simulated_orders
                      .filter((o) => o.status === 'PENDING_AI')
                      .map((order) => (
                        <div key={order.trace_id} className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-3 shadow-sm animate-pulse">
                          <div className="flex justify-between items-start">
                            <div>
                              <div className="text-xs font-bold text-amber-400">{order.strategy_name}</div>
                              <div className="text-[10px] text-gray-500">{order.side} @ {order.entry_price.toFixed(5)}</div>
                            </div>
                            <BrainCircuit className="h-4 w-4 text-amber-500/50" />
                          </div>
                        </div>
                      ))}
                  </div>
                </>
              )}

              {/* Active Trades */}
              <div className="text-xs font-bold text-gray-500 uppercase tracking-wider px-1 mt-4">
                Active Trades ({smcState?.active_orders?.length || 0})
              </div>
              <div className="space-y-2">
                {smcState?.active_orders?.map((order) => (
                  <div key={order.trace_id} className="bg-[#1E222D] border border-gray-800 rounded-xl p-3 shadow-sm">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex flex-col">
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${order.side === 'BUY' ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}`}>
                          {order.side}
                        </span>
                        <span className="text-sm font-bold mt-1 text-gray-200">{order.strategy_name}</span>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-mono text-gray-400">Entry: {order.entry_price.toFixed(5)}</div>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-[10px] text-gray-400">
                      <div className="bg-[#131722] p-1.5 rounded border border-gray-800/50">
                        SL: <span className="text-red-400">{order.sl.toFixed(5)}</span>
                      </div>
                      <div className="bg-[#131722] p-1.5 rounded border border-gray-800/50">
                        TP: <span className="text-green-400">{order.tp.toFixed(5)}</span>
                      </div>
                    </div>
                    {order.ai_audit && (
                      <div className="mt-3 pt-3 border-t border-gray-800/50">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[9px] font-bold text-gray-500 uppercase">AI CONFIDENCE</span>
                          <span className={`text-xs font-black ${order.ai_audit.aci >= 80 ? 'text-green-400' : 'text-amber-400'}`}>
                            {order.ai_audit.aci}%
                          </span>
                        </div>
                        <InstitutionalAudit audit={order.ai_audit} />
                      </div>
                    )}
                  </div>
                ))}
                {!smcState?.active_orders?.length && (
                  <div className="text-xs text-gray-500 italic p-3 text-center border border-dashed border-gray-800 rounded-xl opacity-60">
                    No open positions
                  </div>
                )}
              </div>

              {/* Closed Trades */}
              <div className="text-xs font-bold text-gray-500 uppercase tracking-wider px-1 mt-4">
                Recent Results
              </div>
              <div className="space-y-2">
                {smcState?.closed_orders?.map((order) => (
                  <div key={order.trace_id} className="space-y-1">
                    <div className="bg-[#1E222D]/40 border border-gray-800/50 rounded-xl p-2.5 flex justify-between items-center hover:bg-[#1E222D]/60 transition-colors">
                      <div>
                        <div className="text-xs font-bold text-gray-300">{order.strategy_name}</div>
                        <div className="text-[10px] text-gray-500 flex items-center space-x-1">
                          <span>{new Date(order.close_time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          {order.ai_audit && (
                            <span className={`px-1 rounded-[2px] ${order.ai_audit.aci >= 80 ? 'bg-green-500/10 text-green-500' : 'bg-amber-500/10 text-amber-500'}`}>
                              ACI:{order.ai_audit.aci}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className={`text-sm font-mono font-bold ${order.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        {order.pnl > 0 ? '+' : ''}{order.pnl.toFixed(5)}
                      </div>
                    </div>
                    {order.ai_audit && <InstitutionalAudit audit={order.ai_audit} />}
                  </div>
                ))}
                {!smcState?.closed_orders?.length && (
                  <div className="text-xs text-gray-500 italic p-3 text-center border border-dashed border-gray-800 rounded-xl opacity-60">
                    No recent history
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Settings Modal */}
          {showSettings && (
            <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
              <div className="bg-[#1E222D] border border-gray-800 rounded-xl w-full max-w-md shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
                <div className="p-6 border-b border-gray-800 flex justify-between items-center bg-gray-900/50">
                  <div className="flex items-center space-x-2">
                    <Settings className="h-5 w-5 text-blue-500" />
                    <h3 className="font-bold text-lg">Chart Settings</h3>
                  </div>
                  <button
                    onClick={() => setShowSettings(false)}
                    className="text-gray-500 hover:text-white"
                  >
                    <Zap className="h-5 w-5 rotate-45" /> {/* Close "X" using a rotated icon or just text */}
                  </button>
                </div>

                <div className="p-6 space-y-6">
                  {/* Colors */}
                  <div className="space-y-4">
                    <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">Aesthetics</label>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <label className="text-sm text-gray-300">Line Chart</label>
                        <input
                          type="color"
                          value={settings.lineColor}
                          onChange={(e) => setSettings({ ...settings, lineColor: e.target.value })}
                          className="w-full h-8 bg-transparent cursor-pointer rounded overflow-hidden"
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm text-gray-300">ZigZag</label>
                        <input
                          type="color"
                          value={settings.zigzagColor}
                          onChange={(e) => setSettings({ ...settings, zigzagColor: e.target.value })}
                          className="w-full h-8 bg-transparent cursor-pointer rounded overflow-hidden"
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm text-gray-300">Bullish OB</label>
                        <input
                          type="color"
                          value={settings.bullishOBColor}
                          onChange={(e) => setSettings({ ...settings, bullishOBColor: e.target.value })}
                          className="w-full h-8 bg-transparent cursor-pointer rounded overflow-hidden"
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm text-gray-300">Bearish OB</label>
                        <input
                          type="color"
                          value={settings.bearishOBColor}
                          onChange={(e) => setSettings({ ...settings, bearishOBColor: e.target.value })}
                          className="w-full h-8 bg-transparent cursor-pointer rounded overflow-hidden"
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm text-gray-300">Visible Bars</label>
                        <input
                          type="number"
                          value={settings.visibleBars}
                          onChange={(e) => setSettings({ ...settings, visibleBars: parseInt(e.target.value) || 300 })}
                          min="10"
                          max="1000"
                          className="w-full h-8 bg-gray-900 border border-gray-800 rounded px-2 text-sm text-white focus:ring-blue-500 focus:border-blue-500"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Visibility */}
                  <div className="space-y-4">
                    <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">Visibility</label>
                    <div className="space-y-3">
                      <label className="flex items-center justify-between group cursor-pointer">
                        <span className="text-sm text-gray-200 group-hover:text-white transition-colors">Show HH/LL Labels</span>
                        <input
                          type="checkbox"
                          checked={settings.showLabels}
                          onChange={(e) => setSettings({ ...settings, showLabels: e.target.checked })}
                          className="w-4 h-4 rounded border-gray-800 bg-gray-900 text-blue-600 focus:ring-blue-500"
                        />
                      </label>
                      <label className="flex items-center justify-between group cursor-pointer">
                        <span className="text-sm text-gray-200 group-hover:text-white transition-colors">Show ZigZag Line</span>
                        <input
                          type="checkbox"
                          checked={settings.showZigzag}
                          onChange={(e) => setSettings({ ...settings, showZigzag: e.target.checked })}
                          className="w-4 h-4 rounded border-gray-800 bg-gray-900 text-blue-600 focus:ring-blue-500"
                        />
                      </label>
                      <label className="flex items-center justify-between group cursor-pointer">
                        <span className="text-sm text-gray-200 group-hover:text-white transition-colors">Show CHOCH Lines</span>
                        <input
                          type="checkbox"
                          checked={settings.showCHOCH}
                          onChange={(e) => setSettings({ ...settings, showCHOCH: e.target.checked })}
                          className="w-4 h-4 rounded border-gray-800 bg-gray-900 text-blue-600 focus:ring-blue-500"
                        />
                      </label>
                      <label className="flex items-center justify-between group cursor-pointer">
                        <span className="text-sm text-gray-200 group-hover:text-white transition-colors">Show Order Blocks</span>
                        <input
                          type="checkbox"
                          checked={settings.showOB}
                          onChange={(e) => setSettings({ ...settings, showOB: e.target.checked })}
                          className="w-4 h-4 rounded border-gray-800 bg-gray-900 text-blue-600 focus:ring-blue-500"
                        />
                      </label>
                    </div>
                  </div>
                </div>

                <div className="p-6 bg-gray-900/50 border-t border-gray-800 flex">
                  <button
                    onClick={() => setShowSettings(false)}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 rounded-lg transition-colors shadow-lg shadow-blue-900/20"
                  >
                    Apply Changes
                  </button>
                </div>
              </div>
            </div>
          )}


        </main>
      </div >
    </ClientOnly >
  );
}
