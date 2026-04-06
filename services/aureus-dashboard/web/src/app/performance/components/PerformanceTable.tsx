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

interface PerformanceTableProps {
  trades: Trade[];
  meta: { page: number; page_size: number; total: number; total_pages: number };
  onPageChange: (page: number) => void;
  loading?: boolean;
}

export function PerformanceTable({ trades, meta, onPageChange, loading = false }: PerformanceTableProps) {
  const formatPrice = (price: number | null) => {
    if (price === null) return "—";
    return price.toFixed(price >= 1000 ? 2 : 5);
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "—";
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (loading) {
    return (
      <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-8 text-center">
        <div className="text-gray-500 text-sm">Loading trades...</div>
      </div>
    );
  }

  if (!trades || trades.length === 0) {
    return (
      <div className="bg-[#1E222D] border border-gray-800 rounded-xl p-8 text-center">
        <div className="text-gray-500 text-sm">No trades found for selected filters</div>
      </div>
    );
  }

  return (
    <div className="bg-[#1E222D] border border-gray-800 rounded-xl overflow-hidden">
      <div className="max-h-[400px] overflow-y-auto">
        <table className="w-full text-sm text-left">
          <thead className="text-[10px] text-gray-500 uppercase bg-[#0B0E11]/60 border-b border-gray-800 sticky top-0">
            <tr>
              <th className="px-4 py-3 font-bold">Strategy</th>
              <th className="px-4 py-3 font-bold">Symbol</th>
              <th className="px-4 py-3 font-bold">Side</th>
              <th className="px-4 py-3 font-bold">Entry</th>
              <th className="px-4 py-3 font-bold">Exit</th>
              <th className="px-4 py-3 font-bold">PnL</th>
              <th className="px-4 py-3 font-bold">Date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {trades.map((t) => (
              <tr key={t.id} className="hover:bg-gray-800/20 transition-colors">
                <td className="px-4 py-3 text-xs text-gray-300">{t.strategy_name || "—"}</td>
                <td className="px-4 py-3 text-xs font-bold text-gray-300">{t.symbol}</td>
                <td className="px-4 py-3">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      t.direction === "BUY"
                        ? "bg-green-500/10 text-green-400"
                        : "bg-red-500/10 text-red-400"
                    }`}
                  >
                    {t.direction}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-400">
                  {formatPrice(t.entry_price)}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-400">
                  {formatPrice(t.exit_price)}
                </td>
                <td
                  className={`px-4 py-3 font-bold font-mono text-xs ${
                    t.profit >= 0 ? "text-green-400" : "text-red-400"
                  }`}
                >
                  {t.profit > 0 ? "+" : ""}
                  {t.profit.toFixed(2)}
                </td>
                <td className="px-4 py-3 text-[10px] text-gray-500">
                  {formatDate(t.closed_at || t.filled_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {meta.total_pages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800 bg-[#0B0E11]/40">
          <div className="text-xs text-gray-500">
            Page {meta.page} of {meta.total_pages} ({meta.total} trades)
          </div>
          <div className="flex space-x-2">
            <button
              onClick={() => onPageChange(meta.page - 1)}
              disabled={meta.page <= 1}
              className="px-3 py-1.5 rounded-lg text-xs font-bold transition-colors disabled:opacity-40 disabled:cursor-not-allowed bg-[#1E222D] text-gray-300 hover:bg-gray-800 disabled:hover:bg-[#1E222D]"
            >
              Previous
            </button>
            <button
              onClick={() => onPageChange(meta.page + 1)}
              disabled={meta.page >= meta.total_pages}
              className="px-3 py-1.5 rounded-lg text-xs font-bold transition-colors disabled:opacity-40 disabled:cursor-not-allowed bg-[#1E222D] text-gray-300 hover:bg-gray-800 disabled:hover:bg-[#1E222D]"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
