"use client";

import { useCallback, useEffect, useState } from "react";
import { useSymbols } from "@/context/SymbolsContext";
import { Sidebar } from "@/components/Sidebar";
import ClientOnly from "@/components/ClientOnly";
import { BrainCircuit, Plus, Settings, CheckCircle2, Circle, Trash2, Info, GripVertical, Search } from "lucide-react";
import { DragDropContext, Droppable, Draggable, DropResult, DroppableProvided, DraggableProvided } from "@hello-pangea/dnd";

interface StrategyStep {
    tag: string;
    weight: number;
    required: boolean;
    max_wait: number;
    reset_signals: string[];
}

interface Strategy {
    id?: number;
    name: string;
    description: string;
    min_score: number;
    sequence: StrategyStep[];
    symbols?: string[];
    assigned_symbols?: string[];
    config?: {
        sequence?: StrategyStep[];
    } | string;
    created_at?: string;
}

interface ApiError {
    detail?: string;
}

export default function StrategiesPage() {
    const [selectedSymbol, setSelectedSymbol] = useState<string>("ALL");

    // 0. Initialize selected symbol from localStorage
    useEffect(() => {
        const saved = localStorage.getItem("aureus_selected_symbol");
        if (saved) {
            setSelectedSymbol(saved);
        }
    }, []);
    const [strategies, setStrategies] = useState<Strategy[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [showAssignmentModal, setShowAssignmentModal] = useState(false);
    const [assigningStrategy, setAssigningStrategy] = useState<Strategy | null>(null);
    const [symbolSearch, setSymbolSearch] = useState("");
    const [editStrategyId, setEditStrategyId] = useState<number | null>(null);
    const [newStrategy, setNewStrategy] = useState<Strategy>({
        name: "",
        description: "",
        min_score: 20.0,
        sequence: [{ tag: "ema_200_up", weight: 5.0, required: true, max_wait: 0, reset_signals: [] }],
        symbols: []
    });
    const { symbols: symbolObjects } = useSymbols();
    const allSymbols = symbolObjects.map(s => s.name);

    const AVAILABLE_TAGS = [
        "ema_200_up", "ema_200_down", "ema_100_up", "ema_100_down",
        "ema_55_up", "ema_55_down", "ema_21_up", "ema_21_down",
        "sweep_point", "choch_up", "choch_down", "fvg_up", "fvg_down", "bos_up", "bos_down"
    ];

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";


    // 2. Fetch all strategy templates
    const fetchStrategies = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/strategies`);
            const data = (await res.json()) as Strategy[];
            setStrategies(data);
        } catch (err) {
            console.error("Failed to fetch strategies", err);
        } finally {
            setLoading(false);
        }
    }, [API_BASE]);


    useEffect(() => {
        fetchStrategies();
    }, [fetchStrategies]); // Only fetch strategies once on mount

    const toggleSymbolForStrategy = async (strategyId: number, symbol: string) => {
        try {
            await fetch(`${API_BASE}/symbols/${symbol}/strategies/${strategyId}/toggle`, {
                method: "POST"
            });
            fetchStrategies(); // Refresh global list to see updated tags
        } catch (err) {
            console.error("Toggle failed", err);
        }
    };

    const saveStrategy = async () => {
        try {
            const method = editStrategyId ? "PUT" : "POST";
            const url = editStrategyId ? `${API_BASE}/strategies/${editStrategyId}` : `${API_BASE}/strategies`;

            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: newStrategy.name,
                    description: newStrategy.description,
                    min_score: newStrategy.min_score,
                    config: { sequence: newStrategy.sequence },
                    symbols: newStrategy.symbols // This now correctly saves multiple assignments
                })
            });
            if (res.ok) {
                setShowCreateModal(false);
                setEditStrategyId(null);
                setNewStrategy({
                    name: "",
                    description: "",
                    min_score: 20.0,
                    sequence: [{ tag: "ema_200_up", weight: 5.0, required: true, max_wait: 0, reset_signals: [] }],
                    symbols: []
                });
                fetchStrategies();
            } else {
                const err = (await res.json()) as ApiError;
                alert(err.detail || "Failed to save strategy");
            }
        } catch (err) {
            console.error("Save failed", err);
        }
    };

    const deleteStrategy = async (id: number) => {
        if (!confirm("Are you sure you want to delete this strategy?")) return;
        try {
            const res = await fetch(`${API_BASE}/strategies/${id}`, { method: "DELETE" });
            if (res.ok) {
                fetchStrategies();
            } else {
                const err = (await res.json()) as ApiError;
                alert(err.detail || "Failed to delete strategy");
            }
        } catch (err) {
            console.error("Delete failed", err);
        }
    };

    const openEditModal = (strat: Strategy) => {
        if (strat.id == null) return;
        setEditStrategyId(strat.id);
        const config = (typeof strat.config === 'string' ? JSON.parse(strat.config) : strat.config) || {};
        setNewStrategy({
            id: strat.id,
            name: strat.name,
            description: strat.description || "",
            min_score: strat.min_score,
            sequence: config.sequence || [],
            symbols: strat.assigned_symbols || []
        });
        setShowCreateModal(true);
    };

    const handleAddStep = () => {
        setNewStrategy({
            ...newStrategy,
            sequence: [...newStrategy.sequence, { tag: "sweep_point", weight: 5.0, required: false, max_wait: 0, reset_signals: [] }]
        });
    };

    const toggleSymbolSelection = (symbol: string) => {
        const current = newStrategy.symbols || [];
        if (current.includes(symbol)) {
            setNewStrategy({ ...newStrategy, symbols: current.filter(s => s !== symbol) });
        } else {
            setNewStrategy({ ...newStrategy, symbols: [...current, symbol] });
        }
    };

    const removeStep = (index: number) => {
        setNewStrategy({
            ...newStrategy,
            sequence: newStrategy.sequence.filter((_, i) => i !== index)
        });
    };

    const updateStep = (index: number, field: keyof StrategyStep, value: StrategyStep[keyof StrategyStep]) => {
        const newSeq = [...newStrategy.sequence];
        newSeq[index] = { ...newSeq[index], [field]: value };
        setNewStrategy({ ...newStrategy, sequence: newSeq });
    };

    return (
        <ClientOnly>
            <div className="flex bg-[#131722] min-h-screen text-gray-100 font-inter" suppressHydrationWarning>
                <Sidebar
                    selectedSymbol={selectedSymbol}
                    onSelectSymbol={(s) => {
                        setSelectedSymbol(s);
                        localStorage.setItem("aureus_selected_symbol", s);
                    }}
                    isConnected={true}
                />

                <main className="flex-1 p-8 flex flex-col space-y-8 overflow-y-auto" suppressHydrationWarning>
                    <div className="flex justify-between items-center">
                        <div className="flex items-center space-x-3">
                            <BrainCircuit className="h-8 w-8 text-blue-500" />
                            <div>
                                <h1 className="text-2xl font-bold">Global Strategy Library</h1>
                                <p className="text-gray-400 text-sm">Manage intelligence layers across all markets</p>
                            </div>
                        </div>
                        <button
                            onClick={() => {
                                setEditStrategyId(null);
                                setNewStrategy({ name: "", description: "", min_score: 20.0, sequence: [{ tag: "ema_200_up", weight: 5.0, required: true, max_wait: 0, reset_signals: [] }] });
                                setShowCreateModal(true);
                            }}
                            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-bold flex items-center space-x-2 transition-all shadow-lg shadow-blue-900/20"
                        >
                            <Plus className="h-4 w-4" />
                            <span>Create Strategy</span>
                        </button>
                    </div>

                    {/* Global Management Banner */}
                    <div className="bg-blue-600/5 border border-blue-500/20 p-4 rounded-xl flex items-center justify-between">
                        <div className="flex items-center space-x-4">
                            <Info className="h-5 w-5 text-blue-500" />
                            <div className="flex flex-col">
                                <span className="text-sm text-gray-100 font-semibold">Universal Assignment Mode</span>
                                <span className="text-xs text-gray-400">
                                    Strategies are defined as global templates. Click symbols on any strategy card to assign/unassign them.
                                </span>
                            </div>
                        </div>
                        <div className="flex items-center space-x-2 bg-black/30 p-1 rounded-lg border border-gray-800">
                            <span className="text-[10px] text-gray-500 px-2 font-bold uppercase">Filter:</span>
                            {["ALL", ...allSymbols].map(sym => (
                                <button
                                    key={sym}
                                    onClick={() => setSelectedSymbol(sym)}
                                    className={`px-3 py-1 rounded-md text-[10px] font-bold transition-all ${selectedSymbol === sym
                                        ? 'bg-blue-600 text-white'
                                        : 'text-gray-500 hover:text-gray-300'
                                        }`}
                                >
                                    {sym}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Strategies Grid */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                        {loading ? (
                            <div className="col-span-full py-12 text-center text-gray-500 animate-pulse">Loading strategy library...</div>
                        ) : strategies
                            .filter(s => selectedSymbol === "ALL" || !allSymbols.includes(selectedSymbol) || (s.assigned_symbols || []).includes(selectedSymbol))
                            .map((strat) => (
                                <div
                                    key={strat.id}
                                    className="bg-[#1E222D] border border-gray-800 rounded-xl overflow-hidden transition-all duration-300 hover:border-gray-700"
                                >
                                    <div className="p-4 rounded-xl border border-gray-800 bg-black/20 hover:border-gray-700 transition-all group relative overflow-hidden">
                                        <div className="flex justify-between items-start mb-3">
                                            <div className="flex items-center space-x-3">
                                                <div className="p-2 bg-blue-500/10 rounded-lg group-hover:bg-blue-500/20 transition-colors">
                                                    <BrainCircuit className="h-5 w-5 text-blue-500" />
                                                </div>
                                                <div>
                                                    <h3 className="font-bold text-gray-100">{strat.name}</h3>
                                                    <p className="text-[10px] text-gray-500 font-medium">Template ID: #{strat.id}</p>
                                                </div>
                                            </div>
                                            <div className="flex flex-col items-end">
                                                <span className="text-[10px] font-mono text-blue-400">Min Score: {strat.min_score}</span>
                                                <button
                                                    onClick={() => openEditModal(strat)}
                                                    className="mt-2 p-1 hover:bg-gray-800 rounded transition-colors text-gray-500 hover:text-white"
                                                >
                                                    <Settings className="h-3 w-3" />
                                                </button>
                                            </div>
                                        </div>

                                        {/* Assignments Section (Scalable) */}
                                        <div className="mb-4 space-y-3">
                                            <div className="flex justify-between items-center">
                                                <label className="text-[9px] font-black text-gray-600 uppercase tracking-widest">Active Markets</label>
                                                <button
                                                    onClick={() => {
                                                        setAssigningStrategy(strat);
                                                        setShowAssignmentModal(true);
                                                    }}
                                                    className="flex items-center space-x-1 text-blue-500 hover:text-blue-400 transition-colors"
                                                >
                                                    <Settings className="h-3 w-3" />
                                                    <span className="text-[9px] font-bold">Manage</span>
                                                </button>
                                            </div>
                                            <div className="flex flex-wrap gap-1.5 min-h-[24px]">
                                                {(strat.assigned_symbols || []).slice(0, 6).map((sym: string) => (
                                                    <span
                                                        key={sym}
                                                        className="px-2 py-0.5 rounded bg-blue-600/10 border border-blue-500/20 text-blue-400 text-[9px] font-black"
                                                    >
                                                        {sym}
                                                    </span>
                                                ))}
                                                {(strat.assigned_symbols || []).length > 6 && (
                                                    <span className="px-2 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-400 text-[9px] font-black">
                                                        +{(strat.assigned_symbols || []).length - 6} more
                                                    </span>
                                                )}
                                                {(strat.assigned_symbols || []).length === 0 && (
                                                    <span className="text-[9px] text-gray-600 italic">No markets assigned</span>
                                                )}
                                            </div>
                                        </div>

                                        {/* Sequence Steps */}
                                        <div className="space-y-2 border-t border-gray-800/50 pt-3">
                                            <label className="text-[9px] font-black text-gray-600 uppercase tracking-widest">Signal Logic</label>
                                            <div className="flex flex-wrap gap-1.5">
                                                {(typeof strat.config === 'string' ? JSON.parse(strat.config) : strat.config)?.sequence?.map((step: StrategyStep, idx: number) => (
                                                    <div key={idx} className="flex items-center space-x-1 bg-gray-900/80 border border-gray-800 px-1.5 py-0.5 rounded text-[9px]">
                                                        <span className={step.required ? 'text-blue-400 font-bold' : 'text-gray-500'}>{step.tag}</span>
                                                        <span className="text-gray-700">|</span>
                                                        <span className="text-gray-500">{step.weight}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>

                                        <div className="mt-4 pt-3 border-t border-gray-800 flex justify-between items-center text-[10px]">
                                            <div className="flex space-x-3">
                                                <span className="text-gray-500">
                                                    Created <span className="text-gray-400">{strat.created_at ? new Date(strat.created_at).toLocaleDateString() : "N/A"}</span>
                                                </span>
                                            </div>
                                            <button
                                                onClick={() => strat.id != null && deleteStrategy(strat.id)}
                                                className="flex items-center space-x-1 text-gray-600 hover:text-red-400 transition-colors"
                                            >
                                                <Trash2 className="h-3 w-3" />
                                                <span>Delete Template</span>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))}
                    </div>

                    {/* Empty State */}
                    {!loading && strategies.length === 0 && (
                        <div className="flex flex-col items-center justify-center py-24 space-y-4">
                            <div className="p-4 bg-gray-800/20 rounded-full">
                                <BrainCircuit className="h-12 w-12 text-gray-600" />
                            </div>
                            <div className="text-center">
                                <h3 className="font-bold text-xl">No Strategies Found</h3>
                                <p className="text-gray-500 max-w-xs">Start by creating your first intelligence layer for the platform.</p>
                            </div>
                        </div>
                    )}
                </main>

                {/* Scalable Assignment Modal */}
                {showAssignmentModal && assigningStrategy && (
                    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4">
                        <div className="bg-[#1E222D] border border-gray-800 rounded-xl w-full max-w-lg shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
                            <div className="p-6 border-b border-gray-800 flex justify-between items-center bg-gray-900/50">
                                <div>
                                    <h3 className="font-bold text-lg text-white">Market Assignments</h3>
                                    <p className="text-xs text-gray-500">Manage deployment for <span className="text-blue-400 font-bold">{assigningStrategy.name}</span></p>
                                </div>
                                <button onClick={() => setShowAssignmentModal(false)} className="text-gray-500 hover:text-white transition-colors">
                                    <Trash2 className="h-5 w-5" />
                                </button>
                            </div>

                            <div className="p-4 border-b border-gray-800">
                                <div className="relative">
                                    <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
                                    <input
                                        type="text"
                                        placeholder="Search markets (Forex, Crypto, Indices...)"
                                        value={symbolSearch}
                                        onChange={(e) => setSymbolSearch(e.target.value)}
                                        className="w-full bg-gray-900 border border-gray-800 rounded-lg pl-10 pr-4 py-2 text-sm focus:ring-1 focus:ring-blue-500 outline-none"
                                    />
                                </div>
                            </div>

                            <div className="p-4 max-h-[400px] overflow-y-auto">
                                <div className="grid grid-cols-2 gap-3">
                                    {allSymbols
                                        .filter(s => s.toLowerCase().includes(symbolSearch.toLowerCase()))
                                        .map(sym => {
                                            // Find the latest strategy state from our local list
                                            const currentStrat = strategies.find(s => s.id === assigningStrategy.id);
                                            const isActive = (currentStrat?.assigned_symbols || []).includes(sym);

                                            return (
                                                <button
                                                    key={sym}
                                                    onClick={() => assigningStrategy.id != null && toggleSymbolForStrategy(assigningStrategy.id, sym)}
                                                    className={`flex items-center justify-between p-3 rounded-lg border transition-all ${isActive
                                                        ? 'bg-blue-600/10 border-blue-500/40 text-blue-400'
                                                        : 'bg-gray-900 border-gray-800 text-gray-500 hover:border-gray-700 hover:text-gray-300'
                                                        }`}
                                                >
                                                    <span className="text-xs font-bold uppercase tracking-tight">{sym}</span>
                                                    {isActive ? <CheckCircle2 className="h-4 w-4" /> : <Circle className="h-4 w-4" />}
                                                </button>
                                            );
                                        })}
                                </div>
                                {allSymbols.filter(s => s.toLowerCase().includes(symbolSearch.toLowerCase())).length === 0 && (
                                    <div className="text-center py-12 text-gray-600 italic text-sm">
                                        No markets matching &ldquo;{symbolSearch}&rdquo;
                                    </div>
                                )}
                            </div>

                            <div className="p-6 border-t border-gray-800 bg-gray-900/50 flex justify-end">
                                <button
                                    onClick={() => setShowAssignmentModal(false)}
                                    className="px-8 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold shadow-lg shadow-blue-900/20 transition-all"
                                >
                                    Done
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Create Strategy Modal */}
                {showCreateModal && (
                    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                        <div className="bg-[#1E222D] border border-gray-800 rounded-xl w-full max-w-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
                            <div className="p-6 border-b border-gray-800 flex justify-between items-center bg-gray-900/50">
                                <div className="flex items-center space-x-2">
                                    <Plus className="h-5 w-5 text-blue-500" />
                                    <h3 className="font-bold text-lg text-white">
                                        {editStrategyId ? 'Edit Intelligence Layer' : 'Build Intelligence Layer'}
                                    </h3>
                                </div>
                                <button onClick={() => { setShowCreateModal(false); setEditStrategyId(null); }} className="text-gray-500 hover:text-white transition-colors">
                                    <Trash2 className="h-5 w-5" />
                                </button>
                            </div>

                            <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <label className="text-xs font-bold text-gray-500 uppercase">Strategy Name</label>
                                        <input
                                            type="text"
                                            value={newStrategy.name}
                                            onChange={(e) => setNewStrategy({ ...newStrategy, name: e.target.value })}
                                            className="w-full bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 text-sm focus:ring-1 focus:ring-blue-500 outline-none"
                                            placeholder="e.g. Scalp_Master"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-xs font-bold text-gray-500 uppercase">Min Score Threshold</label>
                                        <input
                                            type="number"
                                            value={newStrategy.min_score}
                                            onChange={(e) => setNewStrategy({ ...newStrategy, min_score: parseFloat(e.target.value) || 0 })}
                                            className="w-full bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 text-sm focus:ring-1 focus:ring-blue-500 outline-none"
                                        />
                                    </div>
                                </div>

                                <div className="space-y-3">
                                    <label className="text-xs font-bold text-gray-500 uppercase tracking-widest">Assign to Symbols</label>
                                    <div className="flex flex-wrap gap-2">
                                        {allSymbols.map(sym => (
                                            <button
                                                key={sym}
                                                type="button"
                                                onClick={() => toggleSymbolSelection(sym)}
                                                className={`px-3 py-1.5 rounded-lg border text-[10px] font-black transition-all ${newStrategy.symbols?.includes(sym) ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-500/20' : 'bg-gray-900 border-gray-800 text-gray-400 hover:border-gray-700'}`}
                                            >
                                                {sym}
                                            </button>
                                        ))}
                                    </div>
                                    <div className="text-[9px] text-gray-500 italic">
                                        Selecting no symbols will make this an unassigned draft.
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-gray-500 uppercase">Description</label>
                                    <textarea
                                        value={newStrategy.description}
                                        onChange={(e) => setNewStrategy({ ...newStrategy, description: e.target.value })}
                                        className="w-full bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 text-sm focus:ring-1 focus:ring-blue-500 outline-none h-20"
                                        placeholder="Briefly describe the confluence logic..."
                                    />
                                </div>

                                {/* Sequence Builder */}
                                <div className="space-y-4">
                                    <div className="flex justify-between items-center">
                                        <label className="text-xs font-bold text-gray-500 uppercase">Signal Sequence (Order Matters)</label>
                                        <button onClick={handleAddStep} className="text-blue-500 text-xs font-bold hover:underline">Add Signal Step</button>
                                    </div>

                                    <DragDropContext onDragEnd={(result: DropResult) => {
                                        if (!result.destination) return;
                                        const items = Array.from(newStrategy.sequence);
                                        const [reorderedItem] = items.splice(result.source.index, 1);
                                        items.splice(result.destination.index, 0, reorderedItem);
                                        setNewStrategy({ ...newStrategy, sequence: items });
                                    }}>
                                        <Droppable droppableId="sequence-list">
                                            {(provided: DroppableProvided) => (
                                                <div
                                                    {...provided.droppableProps}
                                                    ref={provided.innerRef}
                                                    className="space-y-3"
                                                >
                                                    {newStrategy.sequence.map((step, idx) => (
                                                        <Draggable key={`step-${idx}`} draggableId={`step-${idx}`} index={idx}>
                                                            {(provided: DraggableProvided) => (
                                                                <div
                                                                    ref={provided.innerRef}
                                                                    {...provided.draggableProps}
                                                                    className="flex items-center space-x-3 bg-gray-900/50 p-3 rounded-lg border border-gray-800 group"
                                                                >
                                                                    <div {...provided.dragHandleProps} className="cursor-grab hover:text-white text-gray-600">
                                                                        <GripVertical className="h-4 w-4" />
                                                                    </div>
                                                                    <div className="flex-1">
                                                                        <select
                                                                            value={step.tag}
                                                                            onChange={(e) => updateStep(idx, 'tag', e.target.value)}
                                                                            className="w-full bg-transparent text-sm text-gray-200 outline-none"
                                                                        >
                                                                            {AVAILABLE_TAGS.map(t => <option key={t} value={t} className="bg-gray-900">{t}</option>)}
                                                                        </select>
                                                                    </div>
                                                                    <div className="w-20">
                                                                        <input
                                                                            type="number"
                                                                            value={step.weight}
                                                                            onChange={(e) => updateStep(idx, 'weight', parseFloat(e.target.value) || 0)}
                                                                            className="w-full bg-transparent border-b border-gray-700 text-center text-sm font-mono text-blue-400 outline-none focus:border-blue-500 px-1"
                                                                            placeholder="W"
                                                                        />
                                                                    </div>
                                                                    <div className="w-20">
                                                                        <div className="flex flex-col">
                                                                            <input
                                                                                type="number"
                                                                                value={step.max_wait || 0}
                                                                                onChange={(e) => updateStep(idx, 'max_wait', parseInt(e.target.value) || 0)}
                                                                                className="w-full bg-transparent border-b border-gray-700 text-center text-sm font-mono text-yellow-500 outline-none focus:border-yellow-500 px-1"
                                                                                placeholder="0"
                                                                            />
                                                                            <span className="text-[8px] text-gray-500 text-center mt-1">MAX WAIT</span>
                                                                        </div>
                                                                    </div>
                                                                    <div className="flex-1 max-w-[150px]">
                                                                        <div className="flex flex-col space-y-1">
                                                                            <select
                                                                                className="bg-transparent text-[10px] text-red-400 outline-none cursor-pointer border-b border-gray-800 hover:border-red-500 transition-colors"
                                                                                onChange={(e) => {
                                                                                    const val = e.target.value;
                                                                                    if (val && !(step.reset_signals || []).includes(val)) {
                                                                                        updateStep(idx, 'reset_signals', [...(step.reset_signals || []), val]);
                                                                                    }
                                                                                    e.target.value = ""; // Reset dropdown
                                                                                }}
                                                                            >
                                                                                <option value="" className="bg-gray-900">Add Reset Signal...</option>
                                                                                {AVAILABLE_TAGS.map(t => (
                                                                                    <option key={t} value={t} className="bg-gray-900" disabled={(step.reset_signals || []).includes(t)}>
                                                                                        {t}
                                                                                    </option>
                                                                                ))}
                                                                            </select>
                                                                            <div className="flex flex-wrap gap-1 min-h-[16px]">
                                                                                {(step.reset_signals || []).map((rs: string) => (
                                                                                    <span key={rs} className="flex items-center space-x-1 bg-red-500/10 border border-red-500/20 text-[8px] text-red-400 px-1 rounded">
                                                                                        <span>{rs}</span>
                                                                                        <button
                                                                                            onClick={() => updateStep(idx, 'reset_signals', step.reset_signals.filter((s: string) => s !== rs))}
                                                                                            className="hover:text-red-200"
                                                                                        >
                                                                                            ×
                                                                                        </button>
                                                                                    </span>
                                                                                ))}
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                    <label className="flex items-center space-x-2 cursor-pointer">
                                                                        <input
                                                                            type="checkbox"
                                                                            checked={step.required}
                                                                            onChange={(e) => updateStep(idx, 'required', e.target.checked)}
                                                                            className="form-checkbox text-blue-500 rounded bg-gray-800 border-gray-700 focus:ring-blue-500 focus:ring-offset-gray-900"
                                                                        />
                                                                        <span className="text-[10px] uppercase font-bold text-gray-400">Req</span>
                                                                    </label>
                                                                    <button
                                                                        onClick={() => removeStep(idx)}
                                                                        className="p-1.5 text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                                                    >
                                                                        <Trash2 className="h-4 w-4" />
                                                                    </button>
                                                                </div>
                                                            )}
                                                        </Draggable>
                                                    ))}
                                                    {provided.placeholder}
                                                </div>
                                            )}
                                        </Droppable>
                                    </DragDropContext>
                                </div>
                            </div>

                            <div className="p-6 border-t border-gray-800 bg-gray-900/50 flex justify-end space-x-4">
                                <button
                                    onClick={() => { setShowCreateModal(false); setEditStrategyId(null); }}
                                    className="px-6 py-2 rounded-lg font-bold text-gray-400 hover:text-white transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={saveStrategy}
                                    className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold shadow-lg shadow-blue-900/20 transition-all"
                                >
                                    {editStrategyId ? 'Update Matrix' : 'Deploy Matrix'}
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </ClientOnly>
    );
}
