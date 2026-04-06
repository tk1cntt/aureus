"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, AreaSeries } from "lightweight-charts";

interface EquityPoint {
  time: string;
  equity: number;
  pnl: number;
}

interface EquityChartProps {
  data: EquityPoint[];
}

export function EquityChart({ data }: EquityChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#1E222D" },
        textColor: "#9CA3AF",
      },
      grid: {
        vertLines: { color: "#2B2B43" },
        horzLines: { color: "#2B2B43" },
      },
      rightPriceScale: {
        borderColor: "#2B2B43",
      },
      timeScale: {
        borderColor: "#2B2B43",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        mode: 0,
      },
    });

    chartRef.current = chart;

    const areaSeries = chart.addSeries(AreaSeries, {
      topColor: "rgba(59, 130, 246, 0.4)",
      bottomColor: "rgba(59, 130, 246, 0.0)",
      lineColor: "#3B82F6",
      lineWidth: 2,
    });

    // Convert ISO datetime to Unix timestamp (seconds)
    const chartData = data.map((point) => ({
      time: Math.floor(new Date(point.time).getTime() / 1000) as unknown as number,
      value: point.equity,
    }));

    areaSeries.setData(chartData);
    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [data]);

  if (!data || data.length === 0) {
    return (
      <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-2 h-[350px] flex items-center justify-center">
        <div className="text-gray-500 text-sm">No equity data available</div>
      </div>
    );
  }

  return (
    <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-2 h-[350px]">
      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
}
