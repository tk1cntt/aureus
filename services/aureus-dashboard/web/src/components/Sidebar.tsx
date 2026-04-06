"use client";

import { useEffect, useState } from 'react';
import { Search, LayoutDashboard, BrainCircuit, BarChart3, Zap } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useSymbols } from '@/context/SymbolsContext';

interface SidebarProps {
    onSelectSymbol: (s: string) => void;
    selectedSymbol: string;
    isConnected?: boolean;
}

interface SymbolAiStatus {
    sentiment?: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    aci?: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

export const Sidebar = ({ onSelectSymbol, selectedSymbol, isConnected = true }: SidebarProps) => {
    const pathname = usePathname();
    const { symbols } = useSymbols();
    const [statuses, setStatuses] = useState<Record<string, SymbolAiStatus>>({});

    // Fetch AI statuses only
    useEffect(() => {
        const fetchStatuses = async () => {
            try {
                const aiRes = await fetch(`${API_BASE}/ai/all_latest`);
                if (aiRes.ok) {
                    const aiData = await aiRes.json();
                    setStatuses(aiData);
                }
            } catch (err) {
                console.error("Sidebar status fetch error:", err);
            }
        };

        fetchStatuses();
        const interval = setInterval(fetchStatuses, 10000); // Poll every 10s
        return () => clearInterval(interval);
    }, []);

    const handleSelect = (symbolName: string) => {
        localStorage.setItem('aureus_selected_symbol', symbolName);
        onSelectSymbol(symbolName);
    };

    return (
        <div className="w-56 bg-[#0B0E11] border-r border-gray-800 h-screen flex flex-col pt-4" suppressHydrationWarning>
            <div className="px-4 mb-6" suppressHydrationWarning>
                <div className="flex items-center space-x-2 mb-4">
                    <BrainCircuit className="h-6 w-6 text-blue-500" />
                    <h1 className="text-xl font-bold text-white">Aureus</h1>
                </div>

                <nav className="space-y-1 mb-6">
                    <Link
                        href="/"
                        className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${pathname === '/'
                            ? 'bg-blue-600 text-white'
                            : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                            }`}
                    >
                        <LayoutDashboard className="h-4 w-4" />
                        <span>Dashboard</span>
                    </Link>
                    <Link
                        href="/strategies"
                        className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${pathname === '/strategies'
                            ? 'bg-blue-600 text-white'
                            : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                            }`}
                    >
                        <BrainCircuit className="h-4 w-4" />
                        <span>Strategies</span>
                    </Link>
                    <Link
                        href="/backtest"
                        className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${pathname === '/backtest'
                            ? 'bg-blue-600 text-white'
                            : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                            }`}
                    >
                        <BarChart3 className="h-4 w-4" />
                        <span>Backtest</span>
                    </Link>
                    <Link
                        href="/ai-insights"
                        className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${pathname === '/ai-insights'
                            ? 'bg-blue-600 text-white'
                            : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                            }`}
                    >
                        <Zap className="h-4 w-4 text-amber-500" />
                        <span>AI Insights</span>
                    </Link>
                    <Link
                        href="/performance"
                        className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${pathname === '/performance'
                            ? 'bg-blue-600 text-white'
                            : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                            }`}
                    >
                        <BarChart3 className="h-4 w-4" />
                        <span>Performance</span>
                    </Link>
                </nav>

                <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-3 mb-2">
                    Market Watch
                </div>
                <div className="relative" suppressHydrationWarning>
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-gray-500" />
                    <input
                        placeholder="Search symbols..."
                        className="w-full bg-[#1E222D] border-none rounded py-2 pl-8 pr-2 text-sm text-gray-300 focus:ring-1 focus:ring-blue-500"
                    />
                </div>
            </div>

            <div className="flex-1 overflow-y-auto px-2">
                <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-2 mb-2">
                    Pinned Markets
                </div>
                {symbols.map(s => {
                    const symbolName = typeof s === 'string' ? s : s.name;
                    const status = statuses[symbolName];
                    const sentiment = status?.sentiment || 'NEUTRAL';
                    const aci = status?.aci || 0;

                    return (
                        <button
                            key={symbolName}
                            onClick={() => handleSelect(symbolName)}
                            className={`w-full text-left px-3 py-3 rounded-xl mb-2 transition-all relative group ${selectedSymbol === symbolName
                                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                                : 'text-gray-400 hover:bg-[#1E222D] hover:text-white border border-transparent'
                                }`}
                        >
                            <div className="flex justify-between items-center relative z-10">
                                <div className="flex items-center space-x-2">
                                    <div className={`w-2 h-2 rounded-full shadow-[0_0_8px] ${sentiment === 'BULLISH' ? 'bg-green-500 shadow-green-500/50' :
                                        sentiment === 'BEARISH' ? 'bg-red-500 shadow-red-500/50' :
                                            'bg-gray-500 shadow-gray-500/50'
                                        }`} />
                                    <span className="font-bold tracking-tight text-sm uppercase">{symbolName}</span>
                                </div>
                                <div className="flex flex-col items-end">
                                    {aci > 0 && (
                                        <span className={`text-[9px] font-black px-1 rounded-sm ${aci >= 80 ? 'bg-green-500/20 text-green-500' : 'bg-amber-500/20 text-amber-500'}`}>
                                            ACI:{aci}
                                        </span>
                                    )}
                                    <span className="text-[10px] text-gray-500 mt-0.5 group-hover:text-gray-400">Live</span>
                                </div>
                            </div>
                        </button>
                    );
                })}
            </div>

            <div className="p-4 border-t border-gray-800" suppressHydrationWarning>
                <div className="flex items-center space-x-2" suppressHydrationWarning>
                    <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                    <span className="text-xs text-gray-400">
                        {isConnected ? 'Connected to Engine' : 'Syncing...'}
                    </span>
                </div>
            </div>
        </div>
    );
};
