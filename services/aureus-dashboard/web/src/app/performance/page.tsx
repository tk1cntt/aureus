"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useSymbols } from "@/context/SymbolsContext";
import { Sidebar } from "@/components/Sidebar";
import ClientOnly from "@/components/ClientOnly";
import { BarChart3 } from "lucide-react";
import { MetricCard } from "./components/MetricCard";
import { FilterBar } from "./components/FilterBar";
import { PerformanceTable } from "./components/PerformanceTable";
import { EquityChart } from "./components/EquityChart";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

// ---- Type definitions ----

interface MetricsResponse {
  metrics: {
    total_trades: number;
    win_rate: number;
    profit_factor: number;
    max_drawdown: number;
    avg_rr: number;
    sharpe_ratio: number;
    total_profit: number;
    total_loss: number;
    avg_win: number;
    avg_loss: number;
    best_trade: number;
    worst_trade: number;
  };
  meta: {
    symbol: string | null;
    strategy_id: number | null;
    start: string | null;
    end: string | null;
    source: string;
  };
}

interface Trade {
  id: number;
  trace_id: string;
  ticket: number | null;
  symbol: string;
  strategy_name: string | null;
  direction: string;
  entry_price: number | null;
  exit_price: number | null;
  sl: number | null;
  tp: number | null;
  volume: number | null;
  profit: number;
  commission: number;
  swap: number;
  filled_at: string | null;
  closed_at: string | null;
}

interface TradesResponse {
  data: Trade[];
  meta: {
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
    filters: {
      symbol: string | null;
      strategy_id: number | null;
      start: string | null;
      end: string | null;
      status: string;
    };
  };
}

interface EquityPoint {
  time: string;
  equity: number;
  pnl: number;
}

interface EquityCurveResponse {
  data: EquityPoint[];
  meta: {
    source: string;
    points: number;
  };
}

export default function PerformancePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { symbols } = useSymbols();

  // Filter state — initialize from URL params
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return searchParams.get("symbol") || localStorage.getItem("aureus_selected_symbol") || null;
  });
  const [strategyId, setStrategyId] = useState<number | null>(() => {
    if (typeof window === "undefined") return null;
    const val = searchParams.get("strategy_id");
    return val ? Number(val) : null;
  });
  const [startDate, setStartDate] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return searchParams.get("start") || null;
  });
  const [endDate, setEndDate] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return searchParams.get("end") || null;
  });

  // Data state
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [trades, setTrades] = useState<TradesResponse | null>(null);
  const [equityData, setEquityData] = useState<EquityCurveResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);

  // Default dates: end = now, start = 7 days ago
  const now = useMemo(() => new Date(), []);
  const weekAgo = useMemo(() => new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000), [now]);

  const formatDateTime = (date: Date) => {
    const pad = (n: number) => n.toString().padStart(2, "0");
    const y = date.getFullYear();
    const m = pad(date.getMonth() + 1);
    const d = pad(date.getDate());
    const h = pad(date.getHours());
    const i = pad(date.getMinutes());
    return `${y}-${m}-${d}T${h}:${i}`;
  };

  // Set default dates if not provided from URL
  useEffect(() => {
    if (!startDate && !searchParams.get("start")) {
      setStartDate(formatDateTime(weekAgo));
    }
    if (!endDate && !searchParams.get("end")) {
      setEndDate(formatDateTime(now));
    }
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Parallel data fetching
  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedSymbol) params.set("symbol", selectedSymbol);
      if (strategyId) params.set("strategy_id", String(strategyId));
      if (startDate) params.set("start", startDate);
      if (endDate) params.set("end", endDate);
      const qs = params.toString();

      const [metricsRes, tradesRes, equityRes] = await Promise.all([
        fetch(`${API_BASE}/performance/metrics?${qs}`),
        fetch(`${API_BASE}/performance/trades?page=${currentPage}&page_size=20&${qs}`),
        fetch(`${API_BASE}/performance/equity-curve?${qs}`),
      ]);

      const metricsData = (await metricsRes.json()) as MetricsResponse;
      const tradesData = (await tradesRes.json()) as TradesResponse;
      const equityDataRes = (await equityRes.json()) as EquityCurveResponse;

      setMetrics(metricsData);
      setTrades(tradesData);
      setEquityData(equityDataRes);
    } catch (err) {
      console.error("Failed to fetch performance data:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedSymbol, strategyId, startDate, endDate, currentPage]);

  // Fetch on mount and when filters/page change
  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  // Apply filters — update URL and reset page
  const handleApplyFilters = useCallback(
    (filters: {
      symbol: string | null;
      strategyId: number | null;
      startDate: string | null;
      endDate: string | null;
    }) => {
      setSelectedSymbol(filters.symbol);
      setStrategyId(filters.strategyId);
      setStartDate(filters.startDate);
      setEndDate(filters.endDate);
      setCurrentPage(1);

      const params = new URLSearchParams();
      if (filters.symbol) params.set("symbol", filters.symbol);
      if (filters.strategyId) params.set("strategy_id", String(filters.strategyId));
      if (filters.startDate) params.set("start", filters.startDate);
      if (filters.endDate) params.set("end", filters.endDate);

      router.push(`/performance?${params.toString()}`);
    },
    [router]
  );

  // Pagination handler
  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  // Handle symbol selection from Sidebar
  const handleSelectSymbol = useCallback(
    (s: string) => {
      setSelectedSymbol(s);
      localStorage.setItem("aureus_selected_symbol", s);
    },
    []
  );

  return (
    <ClientOnly>
      <div className="flex bg-[#131722] min-h-screen text-gray-100 font-inter">
        <Sidebar
          selectedSymbol={selectedSymbol || ""}
          onSelectSymbol={handleSelectSymbol}
        />

        <main className="flex-1 p-4 space-y-4 overflow-y-auto h-screen">
          {/* Header */}
          <div className="flex justify-between items-center bg-[#1E222D] p-4 rounded-xl border border-gray-800">
            <div className="flex items-center space-x-3">
              <div className="p-2.5 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-lg">
                <BarChart3 className="h-5 w-5 text-blue-400" />
              </div>
              <div>
                <h1 className="text-lg font-bold tracking-tight">Performance Dashboard</h1>
                <p className="text-xs text-gray-500">Live trade performance analytics</p>
              </div>
            </div>
          </div>

          {/* Filter Bar */}
          <FilterBar
            symbol={selectedSymbol}
            strategyId={strategyId}
            startDate={startDate}
            endDate={endDate}
            onApply={handleApplyFilters}
          />

          {/* Metric Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {loading || !metrics?.metrics ? (
              <>
                <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-4 h-[88px] animate-pulse" />
                <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-4 h-[88px] animate-pulse" />
                <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-4 h-[88px] animate-pulse" />
                <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-4 h-[88px] animate-pulse" />
                <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-4 h-[88px] animate-pulse" />
                <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-4 h-[88px] animate-pulse" />
              </>
            ) : (
              <>
                {/* Row 1: Win Rate, Net PnL, Profit Factor */}
                <MetricCard
                  label="Win Rate"
                  value={`${metrics.metrics.win_rate.toFixed(1)}%`}
                  color={metrics.metrics.win_rate >= 50 ? "text-green-400" : "text-red-400"}
                />
                <MetricCard
                  label="Net PnL"
                  value={
                    metrics.metrics.total_profit >= 0
                      ? `+${metrics.metrics.total_profit.toFixed(2)}`
                      : `-${Math.abs(metrics.metrics.total_profit).toFixed(2)}`
                  }
                  color={metrics.metrics.total_profit >= 0 ? "text-green-400" : "text-red-400"}
                />
                <MetricCard
                  label="Profit Factor"
                  value={metrics.metrics.profit_factor.toFixed(2)}
                  color={metrics.metrics.profit_factor >= 1.5 ? "text-green-400" : "text-yellow-400"}
                />
                {/* Row 2: Max Drawdown, Avg R:R, Sharpe Ratio */}
                <MetricCard
                  label="Max Drawdown"
                  value={metrics.metrics.max_drawdown.toFixed(2)}
                  color="text-red-400"
                />
                <MetricCard
                  label="Avg R:R"
                  value={metrics.metrics.avg_rr.toFixed(2)}
                  color={metrics.metrics.avg_rr >= 1 ? "text-green-400" : "text-yellow-400"}
                />
                <MetricCard
                  label="Sharpe Ratio"
                  value={metrics.metrics.sharpe_ratio.toFixed(2)}
                  color={metrics.metrics.sharpe_ratio >= 1 ? "text-green-400" : "text-yellow-400"}
                />
              </>
            )}
          </div>

          {/* Equity Chart */}
          {loading ? (
            <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-2 h-[350px] flex items-center justify-center">
              <div className="text-gray-500 text-sm">Loading chart...</div>
            </div>
          ) : equityData?.data && equityData.data.length > 0 ? (
            <EquityChart data={equityData.data} />
          ) : (
            <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-2 h-[350px] flex items-center justify-center">
              <div className="text-gray-500 text-sm">No equity data available</div>
            </div>
          )}

          {/* Trade History Table */}
          {loading ? (
            <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-8 text-center">
              <div className="text-gray-500 text-sm">Loading trades...</div>
            </div>
          ) : trades?.data && trades.data.length > 0 ? (
            <PerformanceTable
              trades={trades.data}
              meta={trades.meta}
              onPageChange={handlePageChange}
            />
          ) : (
            <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-8 text-center">
              <div className="text-gray-500 text-sm">
                No trades found — adjust filters or wait for live trades
              </div>
            </div>
          )}
        </main>
      </div>
    </ClientOnly>
  );
}
