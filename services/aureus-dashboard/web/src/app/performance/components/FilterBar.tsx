"use client";

import { useCallback, useEffect, useState } from "react";
import { useSymbols } from "@/context/SymbolsContext";

interface Strategy {
  id: number;
  name: string;
}

interface FilterBarProps {
  symbol: string | null;
  strategyId: number | null;
  startDate: string | null;
  endDate: string | null;
  onApply: (filters: {
    symbol: string | null;
    strategyId: number | null;
    startDate: string | null;
    endDate: string | null;
  }) => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

export function FilterBar({ symbol, strategyId, startDate, endDate, onApply }: FilterBarProps) {
  const { symbols } = useSymbols();
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [localSymbol, setLocalSymbol] = useState(symbol ?? "");
  const [localStrategyId, setLocalStrategyId] = useState<number | null>(strategyId);
  const [localStartDate, setLocalStartDate] = useState(startDate ?? "");
  const [localEndDate, setLocalEndDate] = useState(endDate ?? "");

  // Sync props to local state when they change externally
  useEffect(() => {
    setLocalSymbol(symbol ?? "");
  }, [symbol]);

  useEffect(() => {
    setLocalStrategyId(strategyId);
  }, [strategyId]);

  useEffect(() => {
    setLocalStartDate(startDate ?? "");
  }, [startDate]);

  useEffect(() => {
    setLocalEndDate(endDate ?? "");
  }, [endDate]);

  // Load strategies on mount
  useEffect(() => {
    const loadStrategies = async () => {
      try {
        const res = await fetch(`${API_BASE}/strategies`);
        const data = (await res.json()) as Strategy[];
        setStrategies(data);
      } catch (err) {
        console.error("Failed to load strategies for filter:", err);
      }
    };
    void loadStrategies();
  }, []);

  const handleApply = useCallback(() => {
    onApply({
      symbol: localSymbol || null,
      strategyId: localStrategyId,
      startDate: localStartDate || null,
      endDate: localEndDate || null,
    });
  }, [localSymbol, localStrategyId, localStartDate, localEndDate, onApply]);

  return (
    <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-4">
      <div className="flex flex-wrap gap-3 items-end">
        {/* Symbol Dropdown */}
        <div className="space-y-1">
          <label className="text-[10px] text-gray-500 uppercase font-bold">Symbol</label>
          <select
            value={localSymbol}
            onChange={(e) => setLocalSymbol(e.target.value)}
            className="bg-[#0B0E11] border border-gray-800 rounded-lg px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-blue-500/50 text-gray-300"
          >
            <option value="">All symbols</option>
            {symbols.map((s) => {
              const name = typeof s === "string" ? s : s.name;
              return (
                <option key={name} value={name}>
                  {name}
                </option>
              );
            })}
          </select>
        </div>

        {/* Strategy Dropdown */}
        <div className="space-y-1">
          <label className="text-[10px] text-gray-500 uppercase font-bold">Strategy</label>
          <select
            value={localStrategyId ?? ""}
            onChange={(e) => setLocalStrategyId(e.target.value ? Number(e.target.value) : null)}
            className="bg-[#0B0E11] border border-gray-800 rounded-lg px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-blue-500/50 text-gray-300"
          >
            <option value="">All strategies</option>
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        {/* Start Date */}
        <div className="space-y-1">
          <label className="text-[10px] text-gray-500 uppercase font-bold">Start Date</label>
          <input
            type="datetime-local"
            value={localStartDate}
            onChange={(e) => setLocalStartDate(e.target.value)}
            className="bg-[#0B0E11] border border-gray-800 rounded-lg px-3 py-2 text-xs outline-none focus:ring-1 focus:ring-blue-500/50 text-gray-300"
          />
        </div>

        {/* End Date */}
        <div className="space-y-1">
          <label className="text-[10px] text-gray-500 uppercase font-bold">End Date</label>
          <input
            type="datetime-local"
            value={localEndDate}
            onChange={(e) => setLocalEndDate(e.target.value)}
            className="bg-[#0B0E11] border border-gray-800 rounded-lg px-3 py-2 text-xs outline-none focus:ring-1 focus:ring-blue-500/50 text-gray-300"
          />
        </div>

        {/* Apply Button */}
        <button
          onClick={handleApply}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors"
        >
          Apply
        </button>
      </div>
    </div>
  );
}
