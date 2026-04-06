import React from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  color?: string;
  icon?: React.ReactNode;
}

export function MetricCard({ label, value, color = "text-white", icon }: MetricCardProps) {
  return (
    <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] text-gray-500 uppercase font-bold tracking-wider">{label}</span>
        {icon}
      </div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}
